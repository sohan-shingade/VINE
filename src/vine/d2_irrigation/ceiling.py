"""Theoretical CRPS skill ceiling and a filtered historical simulation ensemble (D2).

Sixteenth challenger rung. Rung 14 showed a Gaussian spread around persistence
beats the persistence point mass on CRPS everywhere; this rung asks how much
skill is attainable at all, and builds the ensemble designed to attain it.
Write the h-step innovation as y_t = mu_t + sigma_t * Z with Z the standardized
persistence error. Persistence scored as a point mass has CRPS equal to its
absolute error, so its mean CRPS is mean(sigma_t) * E|Z|. The ideal calibrated
forecaster, the one issuing the true conditional law, has expected CRPS equal
to half the expected Gini mean difference of that law, which standardizes to
mean(sigma_t) * 0.5 * GMD(Z). The maximum attainable CRPS skill vs persistence
is therefore a pure shape functional of the standardized innovation:
ceiling = 1 - 0.5 * GMD(Z) / E|Z|, which for Gaussian Z equals 1 - 1/sqrt(2),
about 0.2929. A filtered historical simulation (FHS) ensemble, the predictive
law mu_t + sigma_t * {z_i} with {z_i} the standardized training-fold
persistence errors, attains the ceiling by construction whenever the
standardized shape is stable between training and test. A second variant,
fhs-adaptive, weights each training error by its own sigma and by exponential
recency before forming the shape, the causal analogue of the sigma-weighted
hindsight optimum, to track seasonal drift of the innovation shape.

Pure numpy/pandas plus the stdlib normal quantile; snapshot I/O stays in the
runner script. Same expanding walk-forward, h-1 label purge, and
identical-rows scoring discipline as every other rung.
"""

from __future__ import annotations

import math
from statistics import NormalDist

import numpy as np
import pandas as pd

from vine.d2_irrigation.config import IrrigationConfig
from vine.d2_irrigation.probabilistic import (
    coverage,
    empirical_crps,
    ewma_sigma_series,
    gaussian_crps,
)
from vine.d5_evaluation.walkforward import expanding_splits, purged_train_slice, skill

# Ceiling for Gaussian standardized innovations: 1 - 1/sqrt(2).
GAUSSIAN_CEILING: float = 1.0 - 1.0 / math.sqrt(2.0)

COVERAGE_QUANTILES = (0.05, 0.25, 0.75, 0.95)

RESULT_COLUMNS = [
    "device",
    "model",
    "horizon_h",
    "n",
    "crps",
    "crps_skill",
    "crps_skill_fold_median",
    "crps_skill_fold_min",
    "ceiling",
    "efficiency",
    "efficiency_fold_min",
    "ceiling_oracle",
    "efficiency_oracle",
    "cov50",
    "cov90",
]


def gini_mean_difference(z: np.ndarray) -> float:
    """Mean absolute difference over all n^2 ordered pairs, including i == j.

    Same denominator convention as the spread term of
    `probabilistic.empirical_crps`. Computed in O(n log n) via a sort: with z
    sorted ascending, the collapsed prefix-sum identity gives
    sum over ordered pairs |z_i - z_j| = 2 * sum_k z_k * (2k - n + 1).

    Args:
        z: one-dimensional sample.

    Returns:
        GMD with the n^2 ordered-pair denominator.

    Raises:
        ValueError: on empty input.
    """
    z = np.asarray(z, dtype=float)
    if z.size == 0:
        raise ValueError("empty input")
    n = z.size
    s = np.sort(z)
    k = np.arange(n, dtype=float)
    return 2.0 * float(np.sum(s * (2.0 * k - n + 1.0))) / (n * n)


def weighted_gini_mean_difference(z: np.ndarray, w: np.ndarray) -> float:
    """Weighted mean absolute difference: sum w_i w_j |z_i - z_j| / (sum w)^2.

    The ordered-pair (diagonal-inclusive) analogue of `gini_mean_difference`,
    which it equals when all weights are equal. Computed in O(n log n) via a
    sort and weighted prefix sums.

    Args:
        z: one-dimensional sample.
        w: nonnegative weights, same shape as z.

    Returns:
        The weighted GMD.

    Raises:
        ValueError: on empty input, shape mismatch, negative weights, or an
            all-zero weight vector.
    """
    z = np.asarray(z, dtype=float)
    w = np.asarray(w, dtype=float)
    if z.size == 0:
        raise ValueError("empty input")
    if w.shape != z.shape:
        raise ValueError("weight shape mismatch")
    if np.any(w < 0) or float(w.sum()) <= 0:
        raise ValueError("weights must be nonnegative with positive sum")
    order = np.argsort(z)
    s, ws = z[order], w[order]
    w_before = np.cumsum(ws) - ws  # total weight strictly below each point
    sw_before = np.cumsum(ws * s) - ws * s  # weighted sum strictly below
    total = 2.0 * float(np.sum(ws * (s * w_before - sw_before)))
    return total / float(w.sum()) ** 2


def skill_ceiling(z: np.ndarray) -> float:
    """Maximum attainable CRPS skill vs persistence for standardized errors z.

    ceiling = 1 - 0.5 * GMD(z) / mean(|z|), a pure shape functional of the
    standardized h-step innovation. For Gaussian z this is `GAUSSIAN_CEILING`.

    Args:
        z: standardized (signed) persistence errors.

    Returns:
        The ceiling, or NaN when len(z) < 2 or mean(|z|) < 1e-12.
    """
    z = np.asarray(z, dtype=float)
    if z.size < 2:
        return float("nan")
    mean_abs = float(np.mean(np.abs(z)))
    if mean_abs < 1e-12:
        return float("nan")
    return 1.0 - 0.5 * gini_mean_difference(z) / mean_abs


def shape_sample(z: np.ndarray, max_sample: int = 512) -> np.ndarray:
    """Sorted copy of z, deterministically thinned to at most max_sample points.

    Thinning takes linspace indices over the sorted array, i.e. equal
    probability quantile points, with no randomness.

    Args:
        z: one-dimensional sample.
        max_sample: maximum number of points to keep.

    Returns:
        Sorted array of at most max_sample values.

    Raises:
        ValueError: on empty input.
    """
    z = np.asarray(z, dtype=float)
    if z.size == 0:
        raise ValueError("empty input")
    s = np.sort(z)
    if s.size > max_sample:
        idx = np.linspace(0, s.size - 1, max_sample).round().astype(int)
        s = s[idx]
    return s


def shape_sample_weighted(z: np.ndarray, w: np.ndarray, max_sample: int = 512) -> np.ndarray:
    """Equal-probability quantile points of the w-weighted law of z.

    Sorts z, places each point at its cumulative-weight midpoint, and
    interpolates the weighted quantile function at max_sample evenly spaced
    probabilities. Deterministic. With equal weights this approximates
    `shape_sample`; unequal weights tilt the shape toward the heavier rows.

    Args:
        z: one-dimensional sample.
        w: nonnegative weights, same shape as z, positive sum.
        max_sample: number of quantile points to return.

    Returns:
        Sorted array of max_sample values representing the weighted law.

    Raises:
        ValueError: on empty input, shape mismatch, negative weights, or an
            all-zero weight vector.
    """
    z = np.asarray(z, dtype=float)
    w = np.asarray(w, dtype=float)
    if z.size == 0:
        raise ValueError("empty input")
    if w.shape != z.shape:
        raise ValueError("weight shape mismatch")
    if np.any(w < 0) or float(w.sum()) <= 0:
        raise ValueError("weights must be nonnegative with positive sum")
    order = np.argsort(z)
    s, ws = z[order], w[order]
    mid = (np.cumsum(ws) - 0.5 * ws) / float(ws.sum())
    probs = (np.arange(max_sample) + 0.5) / max_sample
    return np.interp(probs, mid, s)


def _ratio(num: float, den: float) -> float:
    """num / den, NaN when the denominator is NaN, infinite, or near zero."""
    if not np.isfinite(den) or abs(den) < 1e-12:
        return float("nan")
    return float(num / den)


def _nanmin(values: list[float]) -> float:
    """Minimum of the finite entries, NaN when none are finite."""
    finite = [v for v in values if np.isfinite(v)]
    return float(min(finite)) if finite else float("nan")


def _weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    """Weighted mean over the finite entries, NaN when none are finite."""
    ok = np.isfinite(values)
    if not ok.any() or float(weights[ok].sum()) <= 0:
        return float("nan")
    return float(np.average(values[ok], weights=weights[ok]))


def run_ceiling_experiment(frames: dict[str, pd.DataFrame], cfg: IrrigationConfig) -> pd.DataFrame:
    """Score persistence, the rung-14 Gaussian, and two FHS ensembles vs the ceiling.

    Args:
        frames: {device -> D1 feature frame} containing `cfg.target` on a
            regular hourly grid. Probes are evaluated independently.
        cfg: experiment config; the shared evaluation knobs plus the crps_*
            sigma knobs and `ceiling_max_sample` are used.

    Returns:
        Tidy frame with `RESULT_COLUMNS`: per device, model, and horizon the
        mean CRPS, its skill vs the persistence point mass (aggregate, fold
        median, fold min), the theoretical skill ceiling (valid-row-weighted
        mean of per-fold ceilings), the skill efficiency (skill / ceiling,
        aggregate and worst fold), the oracle ceiling (same shape functional
        computed on the holdout rows themselves, the bound for any sigma-scaled
        single-shape law on this record), its efficiency, and the 50% and 90%
        central-interval coverage. Every model is scored on identical rows: holdout only,
        target and persistence observed, sigma warmed up, fold shape available.
    """
    z_norm = {q: NormalDist().inv_cdf(q) for q in COVERAGE_QUANTILES}
    rows: list[dict] = []
    for device, frame in frames.items():
        y = frame[cfg.target].astype(float)
        splits = expanding_splits(len(y), cfg.n_folds)
        holdout_start = splits[0][1].start
        for h in cfg.horizons_h:
            mu = y.shift(h)  # the persistence level, the shared center
            sig = ewma_sigma_series(y, h, cfg.crps_sigma_halflife, cfg.crps_min_pairs)
            std = (y - mu) / sig  # standardized persistence errors
            ceilings: dict[int, float] = {}
            shapes: dict[int, np.ndarray] = {}
            shapes_adaptive: dict[int, np.ndarray] = {}
            for fold, (tr, _) in enumerate(splits):
                stop = int(purged_train_slice(tr, h - 1).stop or 0)
                s_train = std.iloc[:stop]
                ok = s_train.notna().to_numpy()
                z_train = s_train.to_numpy()[ok]
                if len(z_train) < cfg.crps_min_pairs:
                    continue
                ceilings[fold] = skill_ceiling(z_train)
                shapes[fold] = shape_sample(z_train, cfg.ceiling_max_sample)
                # Adaptive shape: the hindsight optimum on a fold is the
                # sigma-weighted law of its standardized errors, so the causal
                # analogue weights each training error by its own sigma and by
                # exponential recency (halflife in rows), tracking seasonal
                # drift of the innovation shape.
                pos = np.nonzero(ok)[0]
                age = (stop - 1) - pos
                w = sig.iloc[:stop].to_numpy()[ok]
                w = w * np.exp2(-age / cfg.ceiling_shape_halflife)
                shapes_adaptive[fold] = shape_sample_weighted(z_train, w, cfg.ceiling_max_sample)

            valid = y.notna() & mu.notna() & sig.notna()
            valid.iloc[:holdout_start] = False
            for fold, (_, te) in enumerate(splits):
                if fold not in shapes:
                    valid.iloc[te] = False
            n = int(valid.sum())
            if n == 0:
                continue
            fold_info: list[tuple[pd.Series, float, int]] = []
            for fold, (_, te) in enumerate(splits):
                if fold not in shapes:
                    continue
                m = valid.copy()
                m.iloc[: te.start] = False
                m.iloc[te.stop :] = False
                if m.any():
                    fold_info.append((m, ceilings[fold], fold))

            yv, mv = y.to_numpy(), mu.to_numpy()
            crps_series = {
                "persistence-point": (y - mu).abs(),
                "gaussian-ewma": pd.Series(gaussian_crps(yv, mv, sig.to_numpy()), index=y.index),
            }
            q_preds: dict[str, dict[float, pd.Series]] = {
                "persistence-point": dict.fromkeys(COVERAGE_QUANTILES, mu),
                "gaussian-ewma": {q: mu + z_norm[q] * sig for q in COVERAGE_QUANTILES},
            }
            for name, fold_shapes in (("fhs-ewma", shapes), ("fhs-adaptive", shapes_adaptive)):
                crps_v = pd.Series(np.nan, index=y.index, dtype=float)
                q_v = {q: pd.Series(np.nan, index=y.index, dtype=float) for q in COVERAGE_QUANTILES}
                for m, _, fold in fold_info:
                    shape = fold_shapes[fold]
                    u = std[m].to_numpy()
                    # CRPS is positively homogeneous, so scaling the
                    # standardized ensemble CRPS by sigma is exact.
                    crps_v[m] = sig[m].to_numpy() * empirical_crps(shape, u)
                    for q in COVERAGE_QUANTILES:
                        q_v[q][m] = mu[m] + sig[m] * float(np.quantile(shape, q))
                crps_series[name] = crps_v
                q_preds[name] = q_v

            fold_ceilings = np.array([c for _, c, _ in fold_info])
            fold_weights = np.array([float(m.sum()) for m, _, _ in fold_info])
            cell_ceiling = _weighted_mean(fold_ceilings, fold_weights)

            yt = y[valid].to_numpy()
            base = crps_series["persistence-point"]
            base_mean = float(base[valid].mean())
            # Oracle ceiling: the exact hindsight optimum over sigma-scaled
            # single-shape laws, per fold. CRPS is a proper score, so the shape
            # minimizing the realized sigma-weighted CRPS of a fold is the
            # sigma-weighted empirical law of that fold's standardized errors,
            # and its realized total CRPS collapses to
            # 0.5 * weighted_GMD(u, sigma) * sum(sigma). FHS holds one causal
            # shape per fold, so its realized CRPS can never beat this bound;
            # efficiency against it measures true attainment. It uses test
            # rows, so it is a diagnostic yardstick, not a forecast target;
            # the causal `ceiling` column is its training-shape counterpart.
            oracle_total = 0.0
            for m, _, _ in fold_info:
                u_f = std[m].to_numpy()
                w_f = sig[m].to_numpy()
                oracle_total += 0.5 * weighted_gini_mean_difference(u_f, w_f) * float(w_f.sum())
            cell_ceiling_oracle = 1.0 - _ratio(oracle_total / n, base_mean)
            for name, series in crps_series.items():
                mean_crps = float(series[valid].mean())
                fold_skills = [
                    skill(float(series[m].mean()), float(base[m].mean())) for m, _, _ in fold_info
                ]
                cell_skill = skill(mean_crps, base_mean)
                fold_effs = [
                    _ratio(s, c) for s, (_, c, _) in zip(fold_skills, fold_info, strict=True)
                ]
                qp = q_preds[name]
                rows.append(
                    {
                        "device": device,
                        "model": name,
                        "horizon_h": h,
                        "n": n,
                        "crps": mean_crps,
                        "crps_skill": cell_skill,
                        "crps_skill_fold_median": float(np.median(fold_skills)),
                        "crps_skill_fold_min": float(np.min(fold_skills)),
                        "ceiling": cell_ceiling,
                        "efficiency": _ratio(cell_skill, cell_ceiling),
                        "efficiency_fold_min": _nanmin(fold_effs),
                        "ceiling_oracle": cell_ceiling_oracle,
                        "efficiency_oracle": _ratio(cell_skill, cell_ceiling_oracle),
                        "cov50": coverage(
                            yt, qp[0.25][valid].to_numpy(), qp[0.75][valid].to_numpy()
                        ),
                        "cov90": coverage(
                            yt, qp[0.05][valid].to_numpy(), qp[0.95][valid].to_numpy()
                        ),
                    }
                )

    results = pd.DataFrame(rows, columns=RESULT_COLUMNS)
    if len(results):
        results = results.sort_values(["device", "horizon_h", "crps"]).reset_index(drop=True)
    return results

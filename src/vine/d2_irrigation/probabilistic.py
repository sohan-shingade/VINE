"""Probabilistic soil-moisture forecasts scored on CRPS (D2).

Fourteenth challenger family. Thirteen point-forecast families failed to beat
persistence on hourly MAE, so this rung changes the score rather than the
center. CRPS is a proper scoring rule over full predictive distributions. A
deterministic forecast is a point mass whose CRPS equals its absolute error,
so persistence's CRPS baseline equals its MAE, and a forecast with the same
center and an honestly calibrated spread scores strictly better whenever the
calibration is real. Four models are compared per probe and horizon:
persistence as a point mass, a Gaussian around the persistence level with a
causal EWMA error scale, a Gaussian with one fixed per-fold scale, and the
training-fold climatology as an empirical ensemble.

The EWMA scale is an exponentially weighted mean of past absolute h-step
persistence errors, converted to a Gaussian sigma with the half-normal
identity E|X| = sigma * sqrt(2/pi). Absolute errors were chosen over squared
errors for robustness to isolated storm spikes. The estimate used for a
forecast targeting time t comes only from errors whose target time is at or
before the origin t-h, with a warmup minimum and a small sigma floor.
Strictly causal, with the same expanding walk-forward and h-1 label purge as
every other rung. Pure numpy/pandas plus the stdlib normal quantile;
snapshot I/O stays in the runner script.
"""

from __future__ import annotations

import math
from statistics import NormalDist

import numpy as np
import pandas as pd

from vine.d2_irrigation.config import IrrigationConfig
from vine.d5_evaluation.walkforward import expanding_splits, purged_train_slice, skill

# Below this sigma a Gaussian is numerically a point mass; the floor keeps the
# closed form finite on degenerate (e.g. constant) training stretches.
SIGMA_FLOOR = 1e-6

# E|N(0, s^2)| = s * sqrt(2/pi), so a mean absolute error times this constant
# is the matching Gaussian sigma.
ABS_TO_SIGMA = math.sqrt(math.pi / 2.0)

QUANTILES = (0.05, 0.25, 0.5, 0.75, 0.95)

RESULT_COLUMNS = [
    "device",
    "model",
    "horizon_h",
    "n",
    "crps",
    "crps_skill",
    "crps_skill_fold_median",
    "crps_skill_fold_min",
    "pinball_p05",
    "pinball_p25",
    "pinball_p50",
    "pinball_p75",
    "pinball_p95",
    "cov50",
    "cov90",
]

_erf = np.vectorize(math.erf, otypes=[float])


def gaussian_crps(y: np.ndarray, mu: np.ndarray, sigma: np.ndarray) -> np.ndarray:
    """Closed-form CRPS of N(mu, sigma^2) against observations y.

    crps = sigma * (z*(2*Phi(z) - 1) + 2*phi(z) - 1/sqrt(pi)),  z = (y-mu)/sigma.

    sigma = 0 is the point-mass limit and returns |y - mu| exactly; the
    formula converges to that value from below as sigma shrinks.

    Args:
        y: observations.
        mu: predictive means, broadcastable to y.
        sigma: predictive standard deviations, >= 0, broadcastable to y.

    Returns:
        Per-observation CRPS, same shape as y. NaN inputs give NaN.
    """
    y = np.asarray(y, dtype=float)
    mu = np.broadcast_to(np.asarray(mu, dtype=float), y.shape)
    sigma = np.broadcast_to(np.asarray(sigma, dtype=float), y.shape)
    if np.any(sigma < 0):
        raise ValueError("sigma must be non-negative")
    out = np.abs(y - mu)
    out[np.isnan(sigma)] = np.nan
    ok = sigma > 0
    z = (y[ok] - mu[ok]) / sigma[ok]
    phi = np.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi)
    big_phi = 0.5 * (1.0 + _erf(z / math.sqrt(2.0)))
    out[ok] = sigma[ok] * (z * (2.0 * big_phi - 1.0) + 2.0 * phi - 1.0 / math.sqrt(math.pi))
    return out


def empirical_crps(sample: np.ndarray, y: np.ndarray) -> np.ndarray:
    """CRPS of an empirical ensemble against each observation (pooled form).

    crps(y) = mean_i |x_i - y| - 0.5 * mean_{i,j} |x_i - x_j|

    for ensemble members x. The spread term is observation-independent and is
    computed once, so cost is O(m^2 + n*m) for m members and n observations.

    Args:
        sample: ensemble members, one dimension, at least one member.
        y: observations.

    Returns:
        Per-observation CRPS, same shape as y.
    """
    sample = np.asarray(sample, dtype=float)
    y = np.asarray(y, dtype=float)
    if sample.size == 0:
        raise ValueError("empty ensemble")
    term1 = np.mean(np.abs(y[..., None] - sample), axis=-1)
    spread = float(np.mean(np.abs(sample[:, None] - sample[None, :])))
    return term1 - 0.5 * spread


def pinball(y: np.ndarray, pred: np.ndarray, q: float) -> float:
    """Mean pinball (quantile) loss of level-q quantile forecasts `pred`."""
    y = np.asarray(y, dtype=float)
    pred = np.asarray(pred, dtype=float)
    diff = y - pred
    return float(np.mean(np.maximum(q * diff, (q - 1.0) * diff)))


def coverage(y: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> float:
    """Fraction of observations inside the closed interval [lo, hi]."""
    y = np.asarray(y, dtype=float)
    lo = np.asarray(lo, dtype=float)
    hi = np.asarray(hi, dtype=float)
    return float(np.mean((y >= lo) & (y <= hi)))


def ewma_sigma_series(
    y: pd.Series, horizon: int, halflife: float = 72.0, min_pairs: int = 24
) -> pd.Series:
    """Causal h-step persistence-error scale, aligned at target time.

    The value at row t is the sigma for the forecast targeting t: an EWMA of
    absolute h-step persistence errors |y(s) - y(s-h)| over target times
    s <= t - horizon, times `ABS_TO_SIGMA`. Every error in that window was
    realized at or before the forecast origin, so the estimate is causal by
    construction. Errors spanning a gap contain a NaN and drop out; across
    gaps the last estimate is carried forward, which is estimator state,
    never data imputation (same convention as `first_passage`).

    Args:
        y: target series on a regular hourly grid (NaN at gap hours).
        horizon: forecast horizon in rows (hours).
        halflife: EWMA halflife in valid error pairs.
        min_pairs: minimum valid errors before an estimate is emitted.

    Returns:
        sigma aligned to `y.index`, NaN during warmup, floored at SIGMA_FLOOR.
    """
    err = (y - y.shift(horizon)).abs().dropna()
    sig = err.ewm(halflife=halflife).mean() * ABS_TO_SIGMA
    if len(sig):
        sig.iloc[: min_pairs - 1] = np.nan
    known = sig.reindex(y.index).ffill()  # sigma known at each clock hour
    return known.shift(horizon).clip(lower=SIGMA_FLOOR)  # origin t-h -> target t


def fixed_sigma_series(
    y: pd.Series,
    horizon: int,
    n_folds: int,
    min_train: int | None = None,
    min_pairs: int = 24,
) -> pd.Series:
    """One fixed sigma per walk-forward fold, written onto that fold's test rows.

    Per fold the sigma is the mean absolute h-step persistence error over the
    purged training region (errors whose target time precedes the purged
    training stop, so every one is known at the first test row's origin),
    times `ABS_TO_SIGMA`. Folds with fewer than `min_pairs` errors stay NaN.

    Args:
        y: target series on a regular hourly grid.
        horizon: forecast horizon in rows (hours).
        n_folds: expanding walk-forward folds over the holdout region.
        min_train: first holdout row; defaults to half the grid.
        min_pairs: minimum training errors required to emit a sigma.

    Returns:
        sigma aligned to `y.index`: NaN outside test rows, one constant per fold.
    """
    err = (y - y.shift(horizon)).abs()
    out = pd.Series(np.nan, index=y.index, dtype=float)
    for tr, te in expanding_splits(len(y), n_folds, min_train):
        stop = int(purged_train_slice(tr, horizon - 1).stop or 0)
        train_err = err.iloc[:stop].dropna()
        if len(train_err) < min_pairs:
            continue
        out.iloc[te] = max(float(train_err.mean()) * ABS_TO_SIGMA, SIGMA_FLOOR)
    return out


def climatology_sample(y: pd.Series, stop: int, max_sample: int = 300) -> np.ndarray:
    """Deterministic subsample of the training-fold values before row `stop`.

    Takes every observed value in rows [0, stop) and thins it to at most
    `max_sample` chronologically evenly spaced points, so the ensemble spans
    the whole training period without randomness.
    """
    vals = y.iloc[:stop].dropna().to_numpy(dtype=float)
    if len(vals) > max_sample:
        idx = np.linspace(0, len(vals) - 1, max_sample).round().astype(int)
        vals = vals[idx]
    return vals


def run_probabilistic_experiment(
    frames: dict[str, pd.DataFrame], cfg: IrrigationConfig
) -> pd.DataFrame:
    """CRPS-score the four probabilistic models on every probe, per horizon.

    Args:
        frames: {device -> D1 feature frame} containing `cfg.target` on a
            regular hourly grid. Probes are evaluated independently.
        cfg: experiment config; the shared evaluation knobs plus the crps_*
            sigma and ensemble knobs are used.

    Returns:
        Tidy frame with `RESULT_COLUMNS`: per device, model, and horizon the
        mean CRPS, its skill vs the persistence point mass (aggregate, fold
        median, fold min), pinball losses at the five standard quantiles, and
        the 50% and 90% central-interval coverage. Every model is scored on
        identical rows: holdout only, target and persistence observed, both
        sigma estimates warmed up, climatology ensemble available.
    """
    z = {q: NormalDist().inv_cdf(q) for q in QUANTILES}
    rows: list[dict] = []
    for device, frame in frames.items():
        y = frame[cfg.target].astype(float)
        splits = expanding_splits(len(y), cfg.n_folds)
        holdout_start = splits[0][1].start
        for h in cfg.horizons_h:
            mu = y.shift(h)  # the persistence level, the shared center
            sig_ewma = ewma_sigma_series(y, h, cfg.crps_sigma_halflife, cfg.crps_min_pairs)
            sig_fixed = fixed_sigma_series(y, h, cfg.n_folds, min_pairs=cfg.crps_min_pairs)
            samples: dict[int, np.ndarray] = {}
            for fold, (tr, _) in enumerate(splits):
                stop = int(purged_train_slice(tr, h - 1).stop or 0)
                sample = climatology_sample(y, stop, cfg.crps_clim_max_sample)
                if len(sample) >= cfg.crps_min_pairs:
                    samples[fold] = sample

            valid = y.notna() & mu.notna() & sig_ewma.notna() & sig_fixed.notna()
            valid.iloc[:holdout_start] = False
            for fold, (_, te) in enumerate(splits):
                if fold not in samples:
                    valid.iloc[te] = False
            n = int(valid.sum())
            if n == 0:
                continue
            fold_masks = []
            for _, te in splits:
                m = valid.copy()
                m.iloc[: te.start] = False
                m.iloc[te.stop :] = False
                if m.any():
                    fold_masks.append(m)

            yv, mv = y.to_numpy(), mu.to_numpy()
            crps_series = {
                "persistence-point": (y - mu).abs(),
                "gaussian-ewma": pd.Series(
                    gaussian_crps(yv, mv, sig_ewma.to_numpy()), index=y.index
                ),
                "gaussian-fixed": pd.Series(
                    gaussian_crps(yv, mv, sig_fixed.to_numpy()), index=y.index
                ),
            }
            crps_clim = pd.Series(np.nan, index=y.index, dtype=float)
            q_clim = {q: pd.Series(np.nan, index=y.index, dtype=float) for q in QUANTILES}
            for fold, (_, te) in enumerate(splits):
                if fold not in samples:
                    continue
                m = valid.copy()
                m.iloc[: te.start] = False
                m.iloc[te.stop :] = False
                if not m.any():
                    continue
                crps_clim[m] = empirical_crps(samples[fold], y[m].to_numpy())
                for q in QUANTILES:
                    q_clim[q][m] = float(np.quantile(samples[fold], q))
            crps_series["climatology-ensemble"] = crps_clim

            q_preds: dict[str, dict[float, pd.Series]] = {
                "persistence-point": dict.fromkeys(QUANTILES, mu),
                "gaussian-ewma": {q: mu + z[q] * sig_ewma for q in QUANTILES},
                "gaussian-fixed": {q: mu + z[q] * sig_fixed for q in QUANTILES},
                "climatology-ensemble": q_clim,
            }

            yt = y[valid].to_numpy()
            base = crps_series["persistence-point"]
            base_mean = float(base[valid].mean())
            for name, series in crps_series.items():
                mean_crps = float(series[valid].mean())
                fold_skills = [
                    skill(float(series[m].mean()), float(base[m].mean())) for m in fold_masks
                ]
                qp = q_preds[name]
                row = {
                    "device": device,
                    "model": name,
                    "horizon_h": h,
                    "n": n,
                    "crps": mean_crps,
                    "crps_skill": skill(mean_crps, base_mean),
                    "crps_skill_fold_median": float(np.median(fold_skills)),
                    "crps_skill_fold_min": float(np.min(fold_skills)),
                }
                for q in QUANTILES:
                    row[f"pinball_p{round(q * 100):02d}"] = pinball(yt, qp[q][valid].to_numpy(), q)
                row["cov50"] = coverage(yt, qp[0.25][valid].to_numpy(), qp[0.75][valid].to_numpy())
                row["cov90"] = coverage(yt, qp[0.05][valid].to_numpy(), qp[0.95][valid].to_numpy())
                rows.append(row)

    results = pd.DataFrame(rows, columns=RESULT_COLUMNS)
    if len(results):
        results = results.sort_values(["device", "horizon_h", "crps"]).reset_index(drop=True)
    return results

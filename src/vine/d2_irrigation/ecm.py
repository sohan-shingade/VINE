"""Error-correction cross-sensor challenger for soil moisture (D2).

Thirteenth challenger family, borrowed from pairs trading. The five soil
probes share one weather forcing, so their standardized levels may be
cointegrated: a probe that diverges from the cross-section should revert
toward it. The pooled rung stacked every sensor's rows under one regression;
this rung instead uses the cross-sectional divergence itself as the predictor.
Per training fold and per target probe i the forecast is

    y_i(t) + alpha + beta * s_i(t),      s_i(t) = z_i(t) - mean_j(z_j(t))

where z is each probe's level standardized with training-fold constants, the
mean runs over the other probes, and (alpha, beta) come from a closed-form OLS
of the h-step change on the decision-time spread. Strictly causal: constants
and coefficients are fit on the training fold only, with the same h-1 label
purge as every other rung. Rows where any probe is NaN are excluded, never
imputed. Pure numpy/pandas; snapshot I/O stays in the runner script.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from vine.d2_irrigation import baselines
from vine.d2_irrigation.config import IrrigationConfig
from vine.d2_irrigation.pooled import align_frames
from vine.d5_evaluation.metrics import mae, precision_recall, rmse
from vine.d5_evaluation.walkforward import expanding_splits, purged_train_slice, skill

MIN_FIT_ROWS = 20

RESULT_COLUMNS = [
    "device",
    "model",
    "horizon_h",
    "n",
    "mae",
    "rmse",
    "precision",
    "recall",
    "skill_fold_median",
    "skill_fold_min",
    "skill_vs_persistence",
]
DIAGNOSTIC_COLUMNS = ["device", "horizon_h", "fold", "n_fit", "alpha", "beta", "spread_ar1"]


def fit_ecm_ols(spread: np.ndarray, delta: np.ndarray) -> tuple[float, float]:
    """Closed-form OLS of the h-step change on the decision-time spread.

    Args:
        spread: divergence values s_i(t) at decision time, finite only.
        delta: matching changes y_i(t+h) - y_i(t), finite only.

    Returns:
        (alpha, beta). A zero-variance spread gives beta 0 and alpha the mean
        change, so the forecast degrades gracefully to persistence plus drift.
    """
    s_mean, d_mean = float(spread.mean()), float(delta.mean())
    var = float(((spread - s_mean) ** 2).sum())
    if var == 0.0 or not np.isfinite(var):
        return d_mean, 0.0
    beta = float(((spread - s_mean) * (delta - d_mean)).sum() / var)
    return d_mean - beta * s_mean, beta


def spread_ar1(spread: pd.Series) -> float:
    """AR(1) slope of the spread from consecutive-hour pairs.

    Fit s(t+1) = c + phi * s(t) by OLS on pairs where both hours are observed;
    phi below 1 means the spread mean-reverts in sample. Pairs spanning a gap
    contain a NaN and drop out. Returns NaN with fewer than two pairs.
    """
    prev, curr = spread.shift(1), spread
    ok = prev.notna() & curr.notna()
    if int(ok.sum()) < 2:
        return float("nan")
    _, phi = fit_ecm_ols(prev[ok].to_numpy(), curr[ok].to_numpy())
    return phi


def ecm_walk_forward(
    levels: dict[str, pd.Series],
    device: str,
    horizon: int,
    n_folds: int = 5,
    min_train: int | None = None,
    min_fit_rows: int = MIN_FIT_ROWS,
) -> tuple[pd.Series, list[dict[str, float]]]:
    """Causal walk-forward ECM forecasts for one probe at one horizon.

    Args:
        levels: probe level series, all on one shared hourly grid.
        device: the target probe, a key of `levels`.
        horizon: forecast horizon in hours.
        n_folds: expanding walk-forward folds over the holdout region.
        min_train: first holdout row; defaults to half the grid.
        min_fit_rows: folds with fewer usable training rows predict NaN.

    Returns:
        Predictions aligned to the shared grid (row t holds the forecast for
        time t made `horizon` hours earlier) and one diagnostics dict per
        fitted fold with the coefficients and the training spread's AR(1) slope.
    """
    if device not in levels:
        raise ValueError(f"unknown device {device!r}")
    if len(levels) < 2:
        raise ValueError("ECM needs at least two probes")
    index = levels[device].index
    y = levels[device].astype(float)
    lag = y.shift(horizon)
    delta = y - lag
    complete = pd.Series(True, index=index)
    for series in levels.values():
        complete &= series.notna()

    preds = pd.Series(np.nan, index=index, dtype=float)
    diags: list[dict[str, float]] = []
    for fold, (tr, te) in enumerate(expanding_splits(len(index), n_folds, min_train)):
        train = purged_train_slice(tr, horizon - 1)
        stop = int(train.stop or 0)
        known = pd.Series(False, index=index)
        known.iloc[:stop] = True
        stats_rows = complete & known
        if int(stats_rows.sum()) < min_fit_rows:
            continue

        # Standardize every probe with training-fold constants only.
        z: dict[str, pd.Series] = {}
        degenerate = False
        for name, series in levels.items():
            vals = series[stats_rows].astype(float)
            mu, sd = float(vals.mean()), float(vals.std())
            if not np.isfinite(sd) or sd == 0.0:
                degenerate = True
                break
            z[name] = (series.astype(float) - mu) / sd
        if degenerate:
            continue

        # NaN in any other probe propagates through the sum, so partial
        # cross-sections are never averaged over.
        others = [z[name] for name in levels if name != device]
        acc = others[0].copy()
        for series in others[1:]:
            acc = acc + series
        spread = (z[device] - acc / len(others)).where(complete)
        s_lag = spread.shift(horizon)

        fit_ok = known & delta.notna() & s_lag.notna()
        if int(fit_ok.sum()) < min_fit_rows:
            continue
        alpha, beta = fit_ecm_ols(s_lag[fit_ok].to_numpy(), delta[fit_ok].to_numpy())
        preds.iloc[te] = lag.iloc[te] + alpha + beta * s_lag.iloc[te]
        diags.append(
            {
                "fold": fold,
                "n_fit": int(fit_ok.sum()),
                "alpha": alpha,
                "beta": beta,
                "spread_ar1": spread_ar1(spread.where(stats_rows)),
            }
        )
    return preds, diags


def run_ecm_experiment(
    frames: dict[str, pd.DataFrame], cfg: IrrigationConfig
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Walk-forward evaluate the ECM challenger on every probe, per horizon.

    Args:
        frames: {device -> D1 feature frame} containing `cfg.target`. Aligned
            onto one shared hourly grid internally (see `align_frames`).
        cfg: experiment config; only the shared evaluation knobs are used.

    Returns:
        (results, diagnostics). Results follow the shared d5 results schema
        with an `ecm` row and a `persistence` row per probe and horizon,
        scored on identical rows. Diagnostics hold the fitted coefficients
        and the training spread's AR(1) slope per probe, horizon, and fold.
    """
    frames = align_frames(frames)
    levels = {d: f[cfg.target].astype(float) for d, f in frames.items()}
    devices = list(levels)
    n = len(next(iter(levels.values())))

    rows: list[dict] = []
    diag_rows: list[dict] = []
    for h in cfg.horizons_h:
        splits = expanding_splits(n, cfg.n_folds)
        holdout_start = splits[0][1].start
        for d in devices:
            y = levels[d]
            pers = baselines.naive_persistence(y, h)
            pred, diags = ecm_walk_forward(levels, d, h, cfg.n_folds)
            diag_rows.extend({"device": d, "horizon_h": h, **diag} for diag in diags)

            valid = y.notna() & pred.notna() & pers.notna()
            valid.iloc[:holdout_start] = False
            nrows = int(valid.sum())
            if nrows == 0:
                continue
            fold_masks = []
            for _, te in splits:
                m = valid.copy()
                m.iloc[: te.start] = False
                m.iloc[te.stop :] = False
                if m.any():
                    fold_masks.append(m)

            yt = y[valid].to_numpy()
            pv = pers[valid].to_numpy()
            for name, series in (("ecm", pred), ("persistence", pers)):
                yp = series[valid].to_numpy()
                prec, rec = precision_recall(yt < cfg.irrigate_below, yp < cfg.irrigate_below)
                fold_skills = [
                    skill(
                        mae(y[m].to_numpy(), series[m].to_numpy()),
                        mae(y[m].to_numpy(), pers[m].to_numpy()),
                    )
                    for m in fold_masks
                ]
                rows.append(
                    {
                        "device": d,
                        "model": name,
                        "horizon_h": h,
                        "n": nrows,
                        "mae": mae(yt, yp),
                        "rmse": rmse(yt, yp),
                        "precision": prec,
                        "recall": rec,
                        "skill_fold_median": float(np.median(fold_skills)),
                        "skill_fold_min": float(np.min(fold_skills)),
                        "skill_vs_persistence": skill(mae(yt, yp), mae(yt, pv)),
                    }
                )

    results = pd.DataFrame(rows, columns=RESULT_COLUMNS)
    diagnostics = pd.DataFrame(diag_rows, columns=DIAGNOSTIC_COLUMNS)
    if len(results):
        results = results.sort_values(["device", "horizon_h", "mae"]).reset_index(drop=True)
    return results, diagnostics

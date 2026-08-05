"""Barrier-crossing (first-passage) probabilities for soil moisture (D2).

Twelve challenger families failed to beat persistence on the level (MAE).
This module keeps the random walk and changes the question, the same move as
pricing a barrier option: instead of forecasting the level, forecast the
probability that soil moisture falls below the irrigation threshold anywhere
in the next h hours. The series over (t, t+h] is modeled as a Gaussian random
walk with per-hour drift mu and volatility sigma estimated strictly from the
past; the crossing probability then has a closed form via the reflection
principle for Brownian motion with drift.

Pure functions, no I/O. Estimation uses gap-free consecutive-hour pairs only
(gaps are flagged upstream and never imputed). The walk-forward evaluation
lives in scripts/d2_first_passage.py.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

# Below this per-hour sigma the walk is treated as deterministic and the
# crossing probability degenerates to a step function on the drifted level.
SIGMA_FLOOR = 1e-9


def hourly_deltas(series: pd.Series) -> pd.Series:
    """Hourly changes of `series` over gap-free consecutive-hour pairs only.

    A delta exists at time t only when both t and t minus one hour are
    observed and exactly one hour apart. Deltas spanning a missing hour or an
    irregular index step are excluded, never bridged.

    Args:
        series: soil-moisture series on a DatetimeIndex; gaps may appear as
            NaN rows or as missing index entries.

    Returns:
        The valid deltas, indexed by the later timestamp of each pair.
    """
    diff = series.diff()
    step = series.index.to_series().diff() == pd.Timedelta(hours=1)
    return diff[step & diff.notna()]


def ewma_volatility_series(
    series: pd.Series, halflife: float = 72.0, min_pairs: int = 24
) -> pd.Series:
    """Causal per-hour volatility (sigma) estimate at every timestamp.

    An EWMA of squared hourly deltas; the value at time t uses only deltas
    ending at or before t. NaN until `min_pairs` gap-free pairs have
    accumulated. Across data gaps the last estimate is carried forward, which
    is estimator state, never data imputation.

    Args:
        series: hourly soil-moisture series (NaN at gap hours).
        halflife: EWMA halflife in valid pairs.
        min_pairs: minimum gap-free pairs before an estimate is emitted.

    Returns:
        sigma per hour, aligned to `series.index`.
    """
    d = hourly_deltas(series)
    var = (d**2).ewm(halflife=halflife).mean()
    var.iloc[: min_pairs - 1] = np.nan
    return np.sqrt(var).reindex(series.index).ffill()


def ewma_drift_series(series: pd.Series, halflife: float = 336.0, min_pairs: int = 24) -> pd.Series:
    """Causal per-hour drift (mu) estimate at every timestamp.

    A slow EWMA of hourly deltas with the same pairing and warmup rules as
    `ewma_volatility_series`, including the carry-forward across gaps.

    Args:
        series: hourly soil-moisture series (NaN at gap hours).
        halflife: EWMA halflife in valid pairs (slow by default).
        min_pairs: minimum gap-free pairs before an estimate is emitted.

    Returns:
        mu per hour, aligned to `series.index`.
    """
    d = hourly_deltas(series)
    mu = d.ewm(halflife=halflife).mean()
    mu.iloc[: min_pairs - 1] = np.nan
    return mu.reindex(series.index).ffill()


def _ndtr(x: float) -> float:
    """Standard normal CDF via math.erfc (no scipy dependency)."""
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


def _log_ndtr(x: float) -> float:
    """log of the standard normal CDF, stable for very negative x."""
    if x > -10.0:
        return math.log(_ndtr(x))
    # Leading term of the Mills-ratio asymptotic expansion; the neglected
    # correction is O(1/x^2), invisible at the probabilities involved here.
    return -0.5 * x * x - math.log(-x) - 0.5 * math.log(2.0 * math.pi)


def crossing_probability(
    level: float, threshold: float, horizon_h: float, mu: float, sigma: float
) -> float:
    """P(the walk touches or falls below `threshold` somewhere in (t, t+h]).

    For X_s = level + mu*s + sigma*W_s and barrier b = threshold - level < 0,
    the reflection principle with drift gives

        P(min X <= threshold) = Phi((b - mu*h) / (sigma*sqrt(h)))
                              + exp(2*mu*b / sigma^2) * Phi((b + mu*h) / (sigma*sqrt(h)))

    Already at or below the threshold is probability 1. As sigma approaches
    zero the law degenerates to a step function on the drifted level. The
    second term is computed in log space so a strong drying drift cannot
    overflow the exponential.

    Args:
        level: last observed soil moisture at decision time t.
        threshold: barrier (the irrigation trigger, e.g. 25.0).
        horizon_h: window length in hours, > 0.
        mu: per-hour drift.
        sigma: per-hour volatility, >= 0.

    Returns:
        Probability in [0, 1]; NaN if any input is NaN.
    """
    if any(math.isnan(v) for v in (level, threshold, horizon_h, mu, sigma)):
        return float("nan")
    b = threshold - level
    if b >= 0:
        return 1.0
    if sigma <= SIGMA_FLOOR:
        return 1.0 if level + mu * horizon_h <= threshold else 0.0
    s = sigma * math.sqrt(horizon_h)
    p = _ndtr((b - mu * horizon_h) / s)
    log_second = 2.0 * mu * b / (sigma * sigma) + _log_ndtr((b + mu * horizon_h) / s)
    p += math.exp(min(log_second, 0.0))
    return min(max(p, 0.0), 1.0)


def first_passage_probability(
    history: pd.Series,
    horizon_h: float,
    threshold: float,
    sigma_halflife: float = 72.0,
    mu_mode: str = "ewma",
    mu_halflife: float = 336.0,
    min_pairs: int = 24,
) -> float:
    """Crossing probability for the window after the history's last timestamp.

    Convenience wrapper tying estimation to the closed form: sigma (and mu,
    when `mu_mode` is "ewma") come from `history` alone, so the result depends
    only on values at or before decision time.

    Args:
        history: hourly soil moisture up to and including decision time t.
        horizon_h: window length in hours.
        threshold: barrier level.
        sigma_halflife: halflife for the volatility EWMA.
        mu_mode: "ewma" for a slow drift EWMA (the default; it calibrated
            slightly better than zero drift at every horizon in the 2026-08-05
            walk-forward evaluation), "zero" for a driftless walk.
        mu_halflife: halflife for the drift EWMA.
        min_pairs: minimum gap-free pairs before estimates are emitted.

    Returns:
        Probability in [0, 1]; NaN when the level at t is unobserved or too
        few gap-free pairs exist.
    """
    if mu_mode not in ("zero", "ewma"):
        raise ValueError(f"mu_mode must be zero | ewma, got {mu_mode!r}")
    if len(history) == 0 or pd.isna(history.iloc[-1]):
        return float("nan")
    level = float(history.iloc[-1])
    sigma = float(ewma_volatility_series(history, sigma_halflife, min_pairs).iloc[-1])
    if mu_mode == "ewma":
        mu = float(ewma_drift_series(history, mu_halflife, min_pairs).iloc[-1])
    else:
        mu = 0.0
    return crossing_probability(level, threshold, horizon_h, mu, sigma)

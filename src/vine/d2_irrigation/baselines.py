"""Naive and rule-based baselines (D2). Nothing ships unless it beats these (D5).

All series-level predictions are aligned at *target time*: the prediction in
row `t` is for the true value in row `t` and uses only information available
`horizon` rows earlier. That makes baselines pure `shift`s and lets them share
one evaluation path with learned models (see `vine.d2_irrigation.experiment`).
"""

from __future__ import annotations

import pandas as pd


def naive_persistence(series: pd.Series, horizon: int) -> pd.Series:
    """Predict the last observed value for every future step. The floor to beat."""
    return series.shift(horizon)


def seasonal_naive(series: pd.Series, horizon: int, period: int = 24) -> pd.Series:
    """Predict the same time-of-cycle value from the most recent full cycle.

    Soil moisture has a strong daily cycle (irrigation + evapotranspiration),
    so "same hour yesterday" is often a much better floor than persistence.
    Shifts by whole periods, rounded up past `horizon`, so the prediction only
    uses data available at decision time (`t - horizon`).
    """
    shift = period * -(-horizon // period)  # ceil(horizon / period) periods
    return series.shift(shift)


def climatology_hourly(y_train: pd.Series, index: pd.DatetimeIndex) -> pd.Series:
    """Predict the training-window mean for each hour of day.

    The "typical day" baseline: no dynamics at all, just the daily shape.
    Models that can't beat this aren't tracking the actual state.
    """
    by_hour = y_train.groupby(y_train.index.hour).mean()
    return pd.Series(by_hour.reindex(index.hour).to_numpy(), index=index)


def drydown_trend(series: pd.Series, horizon: int, window: int = 24) -> pd.Series:
    """Persistence plus physics: extrapolate the recent drying slope.

    The rule a grower would state out loud — "it's been dropping ~0.1/day, so
    in two days it'll be ~0.2 lower." Slope is the mean change per row over the
    last `window` rows before decision time; prediction is the last observed
    value plus `horizon` rows of that slope. Pure shifts, so row `t` uses only
    data available at `t - horizon`; zero fitted parameters.
    """
    last = series.shift(horizon)
    slope = (last - series.shift(horizon + window)) / window
    return last + horizon * slope


def threshold_rule(moisture: pd.Series, irrigate_below: float) -> pd.Series:
    """Fixed-threshold irrigation decision: irrigate when moisture < threshold."""
    return moisture < irrigate_below

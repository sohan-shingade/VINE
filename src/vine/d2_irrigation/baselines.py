"""Naive and rule-based baselines (D2). Nothing ships unless it beats these (D5).

All series-level predictions are aligned at *target time*: the prediction in
row `t` is for the true value in row `t` and uses only information available
`horizon` rows earlier. That makes baselines pure `shift`s and lets them share
one evaluation path with learned models (see `vine.d2_irrigation.experiment`).
"""

from __future__ import annotations

import numpy as np
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


def hourly_delta_table(y_train: pd.Series) -> pd.Series:
    """Mean hourly change of the target by hour of day, from gap-free pairs only.

    A pair contributes when both hours are observed and the timestamps are
    exactly one hour apart, so sensor gaps are excluded, never imputed. Each
    change `y(k) - y(k-1)` is keyed by `k`, the later hour. Hours with no
    training pairs get 0.0, so the drift falls back to persistence there.

    Args:
        y_train: hourly target series from the training fold only.

    Returns:
        Series of 24 expected hourly changes indexed by hour of day, 0 to 23.
    """
    step = y_train.index.to_series().diff() == pd.Timedelta(hours=1)
    ok = y_train.notna() & y_train.shift(1).notna() & step
    deltas = y_train.diff()[ok]
    table = deltas.groupby(deltas.index.hour).mean()
    return table.reindex(range(24), fill_value=0.0).astype(float)


def _cumulative_drift(table: np.ndarray, horizon: int) -> np.ndarray:
    """Expected change summed over the `horizon` hours ending at each hour of day.

    Entry `hh` is the sum of the hourly change table over the hours keyed
    `hh - horizon + 1` through `hh`, wrapped modulo 24: the drift a forecast
    made `horizon` hours earlier should add on top of persistence.
    """
    offsets = (np.arange(24)[:, None] + np.arange(1 - horizon, 1)[None, :]) % 24
    return table[offsets].sum(axis=1)


def diurnal_drift(y_train: pd.Series, last: pd.Series, horizon: int) -> pd.Series:
    """Persistence plus the expected cumulative hour-of-day drift.

    Soil moisture is near a random walk in levels, yet its hourly changes can
    carry intraday seasonality: evapotranspiration pulls hardest in the
    afternoon and relaxes overnight. The forecast for target time `t` is the
    last observed value at decision time `t - horizon` plus the sum of the
    expected hourly changes for the hours after decision time up to `t`. The
    change table comes from `hourly_delta_table` on the training fold only,
    so the forecast is strictly causal. When every training change is zero
    the forecast equals persistence exactly.

    Args:
        y_train: training-fold target series (fits the hour-of-day table).
        last: last observed value at decision time, aligned to target time
            (the persistence forecast for the rows to predict).
        horizon: forecast horizon in hours.

    Returns:
        Forecast series aligned to `last.index`.
    """
    table = hourly_delta_table(y_train)
    cum = _cumulative_drift(table.to_numpy(), horizon)
    hours = pd.DatetimeIndex(last.index).hour
    return last + cum[hours]


def diurnal_drift_temp(
    y_train: pd.Series,
    temp_train: pd.Series,
    last: pd.Series,
    temp_last: pd.Series,
    horizon: int,
    n_bins: int = 3,
) -> pd.Series:
    """Diurnal drift with the change table conditioned on recent temperature.

    Training pairs are split into `n_bins` quantile bins of the soil
    temperature at the earlier hour of each pair, and one hour-of-day change
    table is fit per bin. At forecast time the bin of the decision-time
    temperature picks the table for the whole horizon window, which stays
    causal. Cells with no training pairs and rows with a missing decision-time
    temperature fall back to the pooled table, so the forecast is defined
    wherever persistence is.

    Args:
        y_train: training-fold target series.
        temp_train: temperature series aligned to `y_train`'s rows.
        last: last observed target value at decision time, aligned to target time.
        temp_last: temperature at decision time, aligned to target time.
        horizon: forecast horizon in hours.
        n_bins: number of temperature quantile bins.

    Returns:
        Forecast series aligned to `last.index`.
    """
    pooled = hourly_delta_table(y_train).to_numpy()
    step = y_train.index.to_series().diff() == pd.Timedelta(hours=1)
    ok = y_train.notna() & y_train.shift(1).notna() & step
    deltas = y_train.diff()[ok]
    temp_at_pair = temp_train.shift(1)[ok]
    usable = temp_at_pair.notna()
    deltas, temp_at_pair = deltas[usable], temp_at_pair[usable]

    if len(temp_at_pair):
        edges = np.quantile(temp_at_pair, [b / n_bins for b in range(1, n_bins)])
    else:
        edges = np.array([])
    pair_bins = np.searchsorted(edges, temp_at_pair.to_numpy(), side="right")
    cum = np.empty((n_bins, 24))
    for b in range(n_bins):
        sub = deltas[pair_bins == b]
        table = sub.groupby(sub.index.hour).mean().reindex(range(24)).to_numpy(dtype=float)
        table = np.where(np.isnan(table), pooled, table)
        cum[b] = _cumulative_drift(table, horizon)
    pooled_cum = _cumulative_drift(pooled, horizon)

    hours = pd.DatetimeIndex(last.index).hour
    temp_vals = temp_last.to_numpy(dtype=float)
    row_bins = np.clip(np.searchsorted(edges, temp_vals, side="right"), 0, n_bins - 1)
    drift = np.where(np.isnan(temp_vals), pooled_cum[hours], cum[row_bins, hours])
    return last + drift


def threshold_rule(moisture: pd.Series, irrigate_below: float) -> pd.Series:
    """Fixed-threshold irrigation decision: irrigate when moisture < threshold."""
    return moisture < irrigate_below

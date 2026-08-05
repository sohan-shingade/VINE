"""Tests for D2 baselines (pure shifts + climatology + diurnal drift)."""

import numpy as np
import pandas as pd

from vine.d2_irrigation.baselines import (
    climatology_hourly,
    diurnal_drift,
    diurnal_drift_temp,
    drydown_trend,
    hourly_delta_table,
    naive_persistence,
    seasonal_naive,
    threshold_rule,
)
from vine.d5_evaluation.walkforward import walk_forward


def _hourly(values):
    idx = pd.date_range("2026-01-01", periods=len(values), freq="1h", tz="UTC")
    return pd.Series(values, index=idx, dtype=float)


def test_persistence_shifts_by_horizon():
    y = _hourly(range(10))
    assert naive_persistence(y, 3).iloc[5] == y.iloc[2]


def test_seasonal_naive_rounds_up_to_whole_periods():
    y = _hourly(range(100))
    # horizon 6 -> one full day back; horizon 30 -> two full days back
    assert seasonal_naive(y, 6, period=24).iloc[50] == y.iloc[26]
    assert seasonal_naive(y, 30, period=24).iloc[60] == y.iloc[12]


def test_seasonal_naive_is_causal():
    """The shifted value must be available at decision time t - horizon."""
    y = _hourly(range(100))
    for h in (1, 6, 24, 30, 48):
        pred = seasonal_naive(y, h)
        used = pred.dropna().iloc[0]  # earliest value the baseline uses
        first_target_pos = int(pred.notna().argmax())
        assert used == y.iloc[0]
        assert first_target_pos >= h  # source observation predates decision time


def test_climatology_predicts_hour_of_day_mean():
    # two days of a repeating daily ramp -> climatology reproduces it exactly
    train = _hourly(list(range(24)) * 2)
    index = pd.date_range("2026-02-01", periods=24, freq="1h", tz="UTC")
    pred = climatology_hourly(train, index)
    assert np.allclose(pred.to_numpy(), np.arange(24))


def test_drydown_trend_is_exact_on_a_linear_ramp():
    """On a perfectly linear dry-down the rule reproduces the truth exactly:
    slope over the window is the true slope, and last + h*slope == y(t)."""
    y = _hourly(np.arange(100, 0, -1))  # steady -1/hour
    pred = drydown_trend(y, horizon=6, window=24)
    assert np.allclose(pred.iloc[40:], y.iloc[40:])
    # needs horizon + window rows of history first
    assert pred.iloc[: 6 + 24].isna().all()


def test_drydown_trend_equals_persistence_when_flat():
    y = _hourly([5.0] * 60)
    pred = drydown_trend(y, horizon=12, window=24)
    assert np.allclose(pred.iloc[40:], 5.0)


def test_threshold_rule():
    y = _hourly([30.0, 24.9, 25.0])
    assert threshold_rule(y, 25.0).tolist() == [False, True, False]


_PATTERN = np.sin(2 * np.pi * np.arange(24) / 24)  # zero net drift over a whole day


def _pattern_series(n_hours: int = 24 * 20) -> pd.Series:
    """Series whose hourly change is exactly `_PATTERN[hour of the later row]`."""
    idx = pd.date_range("2026-01-01", periods=n_hours, freq="1h", tz="UTC")
    deltas = _PATTERN[idx.hour]
    values = 30.0 + np.concatenate([[0.0], np.cumsum(deltas[1:])])
    return pd.Series(values, index=idx)


def test_hourly_delta_table_recovers_a_known_pattern():
    table = hourly_delta_table(_pattern_series().iloc[:240])
    assert np.allclose(table.to_numpy(), _PATTERN)


def test_hourly_delta_table_excludes_gap_pairs():
    y = _hourly(np.arange(200.0))  # steady +1 per hour: every gap-free delta is 1.0
    y.iloc[50] = np.nan  # sensor gap: the pairs (49, 50) and (50, 51) must drop
    holed = y.drop(y.index[100])  # missing row: the 2 h spaced pair around it must drop
    table = hourly_delta_table(holed)
    assert np.allclose(table.to_numpy(), 1.0)


def test_diurnal_drift_forecast_is_exact_on_a_pure_diurnal_series():
    y = _pattern_series()
    for h in (6, 12):
        pred = diurnal_drift(y.iloc[:240], y.shift(h).iloc[240:], h)
        assert np.allclose(pred.to_numpy(), y.iloc[240:].to_numpy())


def test_diurnal_drift_reduces_to_persistence_when_training_deltas_are_zero():
    train = _hourly([7.0] * 100)
    target = _pattern_series(n_hours=48)
    last = target.shift(6)
    pred = diurnal_drift(train, last, 6)
    pd.testing.assert_series_equal(pred, last)


def test_diurnal_drift_poison_tail_causality():
    """Values after the first test row's decision time must not change its
    forecast (same poison-tail pattern as the ARIMA and Prophet tests)."""
    h = 6
    min_train = 120

    def run(series: pd.Series) -> pd.Series:
        pers = series.shift(h)
        X = pd.DataFrame({"soil_water": pers}, index=series.index)
        return walk_forward(
            X,
            series,
            lambda X_tr, y_tr, X_te: diurnal_drift(y_tr, pers[X_te.index], h),
            n_folds=1,
            min_train=min_train,
            purge=h - 1,
        )

    clean = _pattern_series(n_hours=200)
    poisoned = clean.copy()
    poisoned.iloc[min_train - h + 1 :] += 1000.0  # everything past row 0's anchor
    expected = run(clean)
    actual = run(poisoned)
    assert np.isfinite(expected.iloc[min_train])
    assert actual.iloc[min_train] == expected.iloc[min_train]


def test_diurnal_drift_temp_matches_plain_drift_when_temperature_is_flat():
    y = _pattern_series(n_hours=24 * 12)
    temp = pd.Series(20.0, index=y.index)
    h = 6
    train, last = y.iloc[:240], y.shift(h).iloc[240:]
    plain = diurnal_drift(train, last, h)
    conditioned = diurnal_drift_temp(train, temp.iloc[:240], last, temp.shift(h).iloc[240:], h)
    pd.testing.assert_series_equal(conditioned, plain)


def _hot_cold_frame(n_days: int = 20) -> tuple[pd.Series, pd.Series, np.ndarray]:
    """Moisture rising 1/h on hot days and falling 1/h on cold days."""
    idx = pd.date_range("2026-01-01", periods=n_days * 24, freq="1h", tz="UTC")
    hot = np.repeat(np.arange(n_days) % 2 == 0, 24)
    deltas = np.where(hot, 1.0, -1.0)
    values = 100.0 + np.concatenate([[0.0], np.cumsum(deltas[1:])])
    return pd.Series(values, index=idx), pd.Series(np.where(hot, 30.0, 10.0), index=idx), hot


def test_diurnal_drift_temp_conditions_on_decision_time_temperature():
    """The conditioned table must pick the right drift sign from the
    decision-time temperature, while the pooled table averages near zero."""
    y, temp, hot = _hot_cold_frame()
    h = 3
    split = 24 * 16
    last = y.shift(h).iloc[split:]
    pred = diurnal_drift_temp(
        y.iloc[:split], temp.iloc[:split], last, temp.shift(h).iloc[split:], h
    )
    drift = (pred - last).to_numpy()
    hours = pred.index.hour
    midday = hours >= 4  # keep the horizon window inside one temperature regime
    assert np.allclose(drift[hot[split:] & midday], h)
    assert np.allclose(drift[~hot[split:] & midday], -h)


def test_diurnal_drift_temp_missing_temperature_falls_back_to_pooled():
    y, temp, _ = _hot_cold_frame()
    h = 3
    split = 24 * 16
    last = y.shift(h).iloc[split:]
    temp_nan = pd.Series(np.nan, index=last.index)
    fallback = diurnal_drift_temp(y.iloc[:split], temp.iloc[:split], last, temp_nan, h)
    pd.testing.assert_series_equal(fallback, diurnal_drift(y.iloc[:split], last, h))

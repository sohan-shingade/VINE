"""Tests for D2 baselines (pure shifts + climatology)."""

import numpy as np
import pandas as pd

from vine.d2_irrigation.baselines import (
    climatology_hourly,
    drydown_trend,
    naive_persistence,
    seasonal_naive,
    threshold_rule,
)


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

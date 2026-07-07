"""Tests for D2 baselines (pure shifts + climatology)."""

import numpy as np
import pandas as pd

from vine.d2_irrigation.baselines import (
    climatology_hourly,
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


def test_threshold_rule():
    y = _hourly([30.0, 24.9, 25.0])
    assert threshold_rule(y, 25.0).tolist() == [False, True, False]

"""Tests for local D6 persistence irrigation serving."""

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from vine.d6_serving.irrigation import (
    IrrigationServingConfig,
    NoReadingError,
    UnknownBlockError,
    build_irrigation_forecast,
)


def _frame(value=20.0, *, age_h=1.0):
    now = datetime(2026, 7, 23, 12, tzinfo=UTC)
    index = pd.DatetimeIndex([now - timedelta(hours=age_h)])
    return pd.DataFrame({"soil_water": [value]}, index=index), now


def _cfg():
    return IrrigationServingConfig(block_devices={"Cc": "SE01-LS-1"})


def test_persistence_forecast_and_threshold_recommendation():
    frame, now = _frame(20.0)
    result = build_irrigation_forecast("Cc", _cfg(), lambda _: frame, now=now)
    assert result.recommend_irrigation is True
    assert [row.soil_water for row in result.forecast] == [20.0] * 4
    assert result.model == "persistence"
    assert result.data_status == "ok"


def test_exact_threshold_does_not_recommend():
    frame, now = _frame(25.0)
    result = build_irrigation_forecast("Cc", _cfg(), lambda _: frame, now=now)
    assert result.recommend_irrigation is False


def test_stale_reading_suppresses_recommendation():
    frame, now = _frame(20.0, age_h=12.0)
    result = build_irrigation_forecast("Cc", _cfg(), lambda _: frame, now=now)
    assert result.data_status == "stale"
    assert result.recommend_irrigation is None


def test_future_reading_suppresses_recommendation():
    frame, now = _frame(20.0, age_h=-1.0)
    result = build_irrigation_forecast("Cc", _cfg(), lambda _: frame, now=now)
    assert result.data_status == "invalid"
    assert result.recommend_irrigation is None
    assert result.age_hours == -1.0


def test_unknown_block_and_missing_reading_errors():
    frame, now = _frame()
    with pytest.raises(UnknownBlockError):
        build_irrigation_forecast("missing", _cfg(), lambda _: frame, now=now)
    empty = pd.DataFrame({"soil_water": [float("nan")]}, index=frame.index)
    with pytest.raises(NoReadingError):
        build_irrigation_forecast("Cc", _cfg(), lambda _: empty, now=now)


def test_non_finite_readings_are_rejected_and_latest_timestamp_wins():
    frame, now = _frame()
    invalid = pd.DataFrame(
        {"soil_water": [float("inf"), float("-inf"), float("nan")]},
        index=pd.date_range(frame.index[0], periods=3, freq="h"),
    )
    with pytest.raises(NoReadingError, match="no finite"):
        build_irrigation_forecast("Cc", _cfg(), lambda _: invalid, now=now)

    unsorted = pd.DataFrame(
        {"soil_water": [20.0, 30.0]},
        index=[
            pd.Timestamp(now) - pd.Timedelta(hours=1),
            pd.Timestamp(now) - pd.Timedelta(hours=2),
        ],
    )
    result = build_irrigation_forecast("Cc", _cfg(), lambda _: unsorted, now=now)
    assert result.latest_moisture == 20.0
    assert result.recommend_irrigation is True

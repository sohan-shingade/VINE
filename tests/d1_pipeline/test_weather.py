"""Open-Meteo weather reader tests — param building + parsing (no network)."""

import pandas as pd
import pytest

from vine.d1_pipeline import weather


def test_build_archive_params_shape():
    p = weather.build_archive_params("2025-08-01", "2025-08-07", 38.457, -122.896)
    assert p["latitude"] == 38.457
    assert p["longitude"] == -122.896
    assert p["start_date"] == "2025-08-01"
    assert p["end_date"] == "2025-08-07"
    assert p["timezone"] == "UTC"
    # daily vars are comma-joined and include reference ET
    assert "et0_fao_evapotranspiration" in p["daily"]
    assert p["daily"].count(",") == len(weather.DAILY_VARS) - 1


def _fake_payload():
    return {
        "daily": {
            "time": ["2025-08-01", "2025-08-02"],
            "temperature_2m_max": [30.1, 31.4],
            "temperature_2m_min": [12.0, 12.8],
            "precipitation_sum": [0.0, 1.2],
            "et0_fao_evapotranspiration": [6.1, 6.4],
        }
    }


def test_parse_daily_tidy_and_renamed():
    df = weather.parse_daily(_fake_payload())
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df.index.name == "date"
    assert len(df) == 2
    # friendly columns, raw names gone
    assert list(df.columns) == ["temp_max_c", "temp_min_c", "precip_mm", "et0_mm"]
    assert df.loc["2025-08-02", "precip_mm"] == 1.2
    assert df.loc["2025-08-01", "et0_mm"] == 6.1


def test_parse_daily_rejects_error_payload():
    with pytest.raises(ValueError, match="no 'daily'"):
        weather.parse_daily({"error": True, "reason": "bad coords"})


def test_fetch_historical_uses_config_defaults(monkeypatch):
    captured = {}

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return _fake_payload()

    def _fake_get(url, params=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        return _Resp()

    monkeypatch.setattr(weather.requests, "get", _fake_get)
    df = weather.fetch_historical("2025-08-01", "2025-08-02")
    # defaults pulled from settings (vineyard coords + archive url)
    assert captured["url"] == weather.settings.weather_archive_url
    assert captured["params"]["latitude"] == weather.settings.vineyard_lat
    assert captured["params"]["longitude"] == weather.settings.vineyard_lon
    assert len(df) == 2


def test_build_forecast_params_shape():
    p = weather.build_forecast_params(7, 38.457, -122.896)
    assert p["latitude"] == 38.457
    assert p["longitude"] == -122.896
    assert p["forecast_days"] == 7
    assert p["timezone"] == "UTC"
    # daily vars are comma-joined and include reference ET, same as the archive
    assert "et0_fao_evapotranspiration" in p["daily"]
    assert p["daily"].count(",") == len(weather.DAILY_VARS) - 1


def test_parse_daily_handles_forecast_shaped_payload():
    # forecast API returns the same 'daily' block shape as the archive API
    df = weather.parse_daily(_fake_payload())
    assert list(df.columns) == ["temp_max_c", "temp_min_c", "precip_mm", "et0_mm"]
    assert len(df) == 2


def test_fetch_forecast_uses_config_defaults(monkeypatch):
    captured = {}

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return _fake_payload()

    def _fake_get(url, params=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        return _Resp()

    monkeypatch.setattr(weather.requests, "get", _fake_get)
    df = weather.fetch_forecast(days=3)
    # defaults pulled from settings (vineyard coords + forecast url)
    assert captured["url"] == weather.settings.weather_forecast_url
    assert captured["params"]["latitude"] == weather.settings.vineyard_lat
    assert captured["params"]["longitude"] == weather.settings.vineyard_lon
    assert captured["params"]["forecast_days"] == 3
    assert len(df) == 2


def test_vintage_lag_days_rounds_lead_up_never_fresher():
    # Causality: the previous_dayN run for target hour τ was issued no later
    # than τ - 24·N, and every hour in a decision's (t, t+h] window satisfies
    # τ ≤ t + h — so run issue time ≤ t requires 24·N ≥ h, for every horizon.
    assert weather.vintage_lag_days(6) == 1
    assert weather.vintage_lag_days(12) == 1
    assert weather.vintage_lag_days(24) == 1
    assert weather.vintage_lag_days(25) == 2
    assert weather.vintage_lag_days(48) == 2
    for h in range(1, 97):
        assert 24 * weather.vintage_lag_days(h) >= h  # issued at or before t
    with pytest.raises(ValueError, match="positive"):
        weather.vintage_lag_days(0)


def test_build_previous_runs_params_shape():
    p = weather.build_previous_runs_params("2026-01-22", "2026-07-08", 38.457, -122.896)
    assert p["latitude"] == 38.457
    assert p["longitude"] == -122.896
    assert p["start_date"] == "2026-01-22"
    assert p["end_date"] == "2026-07-08"
    assert p["timezone"] == "UTC"
    # every hourly var requested at every vintage lag
    names = p["hourly"].split(",")
    assert "precipitation_previous_day1" in names
    assert "et0_fao_evapotranspiration_previous_day2" in names
    assert len(names) == len(weather.HOURLY_VINTAGE_VARS) * 2


def _fake_vintage_payload():
    return {
        "hourly": {
            "time": ["2026-01-22T00:00", "2026-01-22T01:00", "2026-01-22T02:00"],
            "precipitation_previous_day1": [0.0, 0.1, 0.2],
            "precipitation_previous_day2": [0.0, 0.0, 0.3],
            "et0_fao_evapotranspiration_previous_day1": [0.09, 0.03, 0.02],
            "et0_fao_evapotranspiration_previous_day2": [0.08, 0.04, None],
        }
    }


def test_parse_hourly_vintages_tidy_and_renamed():
    df = weather.parse_hourly_vintages(_fake_vintage_payload())
    assert isinstance(df.index, pd.DatetimeIndex)
    assert list(df.columns) == [
        "precip_mm_prev1",
        "precip_mm_prev2",
        "et0_mm_prev1",
        "et0_mm_prev2",
    ]
    assert df["precip_mm_prev2"].iloc[2] == 0.3
    assert pd.isna(df["et0_mm_prev2"].iloc[2])  # missing hours stay NaN


def test_parse_hourly_vintages_rejects_error_payload():
    with pytest.raises(ValueError, match="no 'hourly'"):
        weather.parse_hourly_vintages({"error": True, "reason": "bad coords"})


def test_fetch_forecast_vintages_uses_config_defaults(monkeypatch):
    captured = {}

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return _fake_vintage_payload()

    def _fake_get(url, params=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        return _Resp()

    monkeypatch.setattr(weather.requests, "get", _fake_get)
    df = weather.fetch_forecast_vintages("2026-01-22", "2026-01-22")
    assert captured["url"] == weather.settings.weather_previous_runs_url
    assert captured["params"]["latitude"] == weather.settings.vineyard_lat
    assert captured["params"]["longitude"] == weather.settings.vineyard_lon
    assert len(df) == 3

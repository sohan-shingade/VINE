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

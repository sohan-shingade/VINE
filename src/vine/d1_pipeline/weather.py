"""Weather for IHV from the Open-Meteo Archive + Forecast APIs (D1 input #4).

Weather drives irrigation (evapotranspiration, rainfall) and harvest timing
(growing degree-days). The on-site LoRaWAN sensors give local point weather but
are recent-only and gappy, so historical features come from a reanalysis
archive instead (see docs/adr/0009-weather-data-sources.md). Forecast weather
(input 4f) gives D2 irrigation true lead-time features — the physical reason a
model should be able to beat a persistence baseline.

    Archive (ERA5, past):  https://archive-api.open-meteo.com/v1/archive
    Forecast (future):     https://api.open-meteo.com/v1/forecast
    Both free, no API key, gridded to the vineyard coords (38.457, -122.896).

Both endpoints return a tidy daily frame indexed by date with friendly column
names. The query/parse helpers are pure (network-free) so they unit-test
without a live call; `fetch_historical`/`fetch_forecast` are the thin I/O
edges. `requests` is a core dependency.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import requests

from vine.common.config import settings
from vine.common.logging import get_logger

log = get_logger(__name__)

# Daily variables we pull from the archive (raw Open-Meteo names).
DAILY_VARS: tuple[str, ...] = (
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
    "et0_fao_evapotranspiration",  # reference ET (FAO-56) — atmospheric demand
)

# Raw Open-Meteo names -> friendly column names used downstream.
_RENAME: dict[str, str] = {
    "temperature_2m_max": "temp_max_c",
    "temperature_2m_min": "temp_min_c",
    "precipitation_sum": "precip_mm",
    "et0_fao_evapotranspiration": "et0_mm",
}


def build_archive_params(
    start_date: str,
    end_date: str,
    lat: float,
    lon: float,
    daily: tuple[str, ...] = DAILY_VARS,
    timezone: str = "UTC",
) -> dict[str, Any]:
    """Build query params for the Open-Meteo archive endpoint.

    Dates are inclusive ISO ``YYYY-MM-DD`` strings.
    """
    return {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "daily": ",".join(daily),
        "timezone": timezone,
    }


def parse_daily(payload: dict[str, Any]) -> pd.DataFrame:
    """Parse an Open-Meteo archive JSON response into a tidy daily frame.

    Indexed by ``date`` (UTC), columns renamed to friendly names. Raises if the
    response has no ``daily`` block (e.g. an API error payload).
    """
    if "daily" not in payload:
        raise ValueError(
            f"no 'daily' block in Open-Meteo response: {payload.get('reason', payload)}"
        )
    df = pd.DataFrame(payload["daily"])
    df["time"] = pd.to_datetime(df["time"])
    df = df.set_index("time").rename(columns=_RENAME)
    df.index.name = "date"
    return df


def build_forecast_params(
    days: int,
    lat: float,
    lon: float,
    daily: tuple[str, ...] = DAILY_VARS,
    timezone: str = "UTC",
) -> dict[str, Any]:
    """Build query params for the Open-Meteo forecast endpoint.

    `days` is the forecast horizon in days (Open-Meteo accepts 1..16).
    """
    return {
        "latitude": lat,
        "longitude": lon,
        "forecast_days": days,
        "daily": ",".join(daily),
        "timezone": timezone,
    }


def fetch_historical(
    start_date: str,
    end_date: str,
    lat: float | None = None,
    lon: float | None = None,
    daily: tuple[str, ...] = DAILY_VARS,
    url: str | None = None,
    timeout: float = 30.0,
) -> pd.DataFrame:
    """Fetch daily historical weather for the vineyard over [start, end].

    Coordinates and the archive URL default to the configured vineyard location
    (see vine.common.config). Returns the tidy frame from `parse_daily`.
    """
    lat = settings.vineyard_lat if lat is None else lat
    lon = settings.vineyard_lon if lon is None else lon
    url = url or settings.weather_archive_url
    params = build_archive_params(start_date, end_date, lat, lon, daily)
    resp = requests.get(url, params=params, timeout=timeout)
    resp.raise_for_status()
    df = parse_daily(resp.json())
    log.info("weather fetch", rows=len(df), start=start_date, end=end_date)
    return df


def fetch_forecast(
    days: int = 7,
    lat: float | None = None,
    lon: float | None = None,
    daily: tuple[str, ...] = DAILY_VARS,
    url: str | None = None,
    timeout: float = 30.0,
) -> pd.DataFrame:
    """Fetch a daily weather forecast for the vineyard, `days` ahead.

    Coordinates and the forecast URL default to the configured vineyard
    location (see vine.common.config). The response's `daily` block has the
    same shape as the archive API, so it reuses `parse_daily`. Returns the
    tidy frame (today .. today + days - 1).
    """
    lat = settings.vineyard_lat if lat is None else lat
    lon = settings.vineyard_lon if lon is None else lon
    url = url or settings.weather_forecast_url
    params = build_forecast_params(days, lat, lon, daily)
    resp = requests.get(url, params=params, timeout=timeout)
    resp.raise_for_status()
    df = parse_daily(resp.json())
    log.info("weather forecast fetch", rows=len(df), days=days)
    return df

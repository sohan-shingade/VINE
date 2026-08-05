"""Weather for IHV from the Open-Meteo Archive + Forecast APIs (D1 input #4).

Weather drives irrigation (evapotranspiration, rainfall) and harvest timing
(growing degree-days). The on-site LoRaWAN sensors give local point weather but
are recent-only and gappy, so historical features come from a reanalysis
archive instead (see docs/adr/0009-weather-data-sources.md). Forecast weather
(input 4f) gives D2 irrigation true lead-time features — the physical reason a
model should be able to beat a persistence baseline.

    Archive (ERA5, past):  https://archive-api.open-meteo.com/v1/archive
    Forecast (future):     https://api.open-meteo.com/v1/forecast
    Previous runs (as-issued forecasts): https://previous-runs-api.open-meteo.com/v1/forecast
    All free, no API key, gridded to the vineyard coords (38.457, -122.896).

The Previous Runs API serves REAL archived forecast vintages: hourly variables
with a `_previous_dayN` suffix give what the model run issued N days earlier
predicted for each timestamp. That is what turns D2's perfect-forecast backtest
into an honest one — the model sees what a forecaster actually said, not what
the weather actually did.

All endpoints return tidy frames with friendly column names. The query/parse
helpers are pure (network-free) so they unit-test without a live call;
`fetch_historical`/`fetch_forecast`/`fetch_forecast_vintages` are the thin I/O
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

# Hourly variables we pull as forecast vintages (raw Open-Meteo names). Each
# hourly value at timestamp τ covers the PRECEDING hour (τ-1h, τ].
HOURLY_VINTAGE_VARS: tuple[str, ...] = ("precipitation", "et0_fao_evapotranspiration")

# Raw hourly stems -> friendly stems; a `_previous_dayN` suffix maps to `_prevN`
# (e.g. `precipitation_previous_day2` -> `precip_mm_prev2`).
_VINTAGE_RENAME: dict[str, str] = {
    "precipitation": "precip_mm",
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


def vintage_lag_days(horizon_h: int) -> int:
    """Smallest `_previous_dayN` lag that is causally safe for an `horizon_h` lead.

    Causality: a decision at time t with horizon h reads forecast values for
    target hours τ ∈ (t, t+h], so every value must come from a run issued at or
    before t. The `_previous_dayN` value at τ comes from the run 24·N hours
    older than the freshest archived run for τ, which in the worst case was
    issued right at τ. So the vintage run was issued no later than τ − 24·N,
    and `τ − 24·N ≤ t` for every τ in the window iff `24·N ≥ h`. Round the lead
    UP to whole days — never borrow a fresher run than causally available.
    """
    if horizon_h <= 0:
        raise ValueError("horizon must be positive")
    return -(-horizon_h // 24)  # ceil(h / 24)


def build_previous_runs_params(
    start_date: str,
    end_date: str,
    lat: float,
    lon: float,
    hourly: tuple[str, ...] = HOURLY_VINTAGE_VARS,
    lag_days: tuple[int, ...] = (1, 2),
    timezone: str = "UTC",
) -> dict[str, Any]:
    """Build query params for the Open-Meteo previous-runs endpoint.

    Requests each hourly variable at each `_previous_dayN` lag (real forecast
    vintages, N days stale). Dates are inclusive ISO ``YYYY-MM-DD`` strings.
    """
    names = [f"{var}_previous_day{n}" for var in hourly for n in lag_days]
    return {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": ",".join(names),
        "timezone": timezone,
    }


def parse_hourly_vintages(payload: dict[str, Any]) -> pd.DataFrame:
    """Parse an Open-Meteo previous-runs JSON response into a tidy hourly frame.

    Indexed by hourly UTC ``time``; `{var}_previous_dayN` columns become
    `{friendly}_prevN` (e.g. `et0_mm_prev2`). Missing hours stay NaN — gaps are
    flagged downstream, never imputed. Raises on error payloads.
    """
    if "hourly" not in payload:
        raise ValueError(
            f"no 'hourly' block in Open-Meteo response: {payload.get('reason', payload)}"
        )
    df = pd.DataFrame(payload["hourly"])
    df["time"] = pd.to_datetime(df["time"])
    df = df.set_index("time")
    rename = {}
    for column in df.columns:
        stem, _, lag = column.partition("_previous_day")
        if stem in _VINTAGE_RENAME and lag.isdigit():
            rename[column] = f"{_VINTAGE_RENAME[stem]}_prev{int(lag)}"
    return df.rename(columns=rename)


def fetch_forecast_vintages(
    start_date: str,
    end_date: str,
    lat: float | None = None,
    lon: float | None = None,
    hourly: tuple[str, ...] = HOURLY_VINTAGE_VARS,
    lag_days: tuple[int, ...] = (1, 2),
    url: str | None = None,
    timeout: float = 60.0,
) -> pd.DataFrame:
    """Fetch archived hourly forecast vintages for the vineyard over [start, end].

    Real as-issued forecasts (not realized weather): each `_prevN` column holds
    what the run N days earlier predicted for that hour. Coordinates and the
    previous-runs URL default to the configured vineyard location.
    """
    lat = settings.vineyard_lat if lat is None else lat
    lon = settings.vineyard_lon if lon is None else lon
    url = url or settings.weather_previous_runs_url
    params = build_previous_runs_params(start_date, end_date, lat, lon, hourly, lag_days)
    resp = requests.get(url, params=params, timeout=timeout)
    resp.raise_for_status()
    df = parse_hourly_vintages(resp.json())
    log.info("weather vintage fetch", rows=len(df), start=start_date, end=end_date)
    return df

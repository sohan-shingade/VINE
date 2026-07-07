"""D1 ingestion entrypoint: pull IHV sensors from InfluxDB to local snapshots.

Pulls each device's relevant measurements, tidies them, and writes one Parquet
per device under `data/raw/sensors/`. Those snapshots are then pinned with DVC
(`dvc add data/raw/sensors`) so every model trains on a known data version.

Run locally (`vine ingest --start -7d`) or as an NRP CronJob (see
`k8s/ihv/ingest-cronjob.yaml`). Requires the `sensors` extra.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from vine.common import get_logger, settings
from vine.d1_pipeline.influx import DEVICES, InfluxReader
from vine.d1_pipeline.weather import fetch_historical

log = get_logger(__name__)

# Which measurements to pull per device kind.
KIND_MEASUREMENTS: dict[str, list[str]] = {
    "soil": ["soil_conductivity", "soil_temperature", "soil_water"],
    "soil_profile": [
        # multi-depth probe — raw names with SOIL1..SOIL4 suffixes
        "device_frmpayload_data_conduct_SOIL1",
        "device_frmpayload_data_temp_SOIL1",
        "device_frmpayload_data_water_SOIL1",
    ],
    "air": ["co2", "humidity", "temperature", "pressure"],
}


def ingest_all(start: str = "-7d", out_dir: Path | None = None) -> dict[str, int]:
    """Pull every known device since `start`, write a Parquet per device.

    Returns a {device_name: row_count} summary. Devices with no data are skipped.
    """
    reader = InfluxReader()
    out_dir = out_dir or (settings.data_dir / "raw" / "sensors")
    out_dir.mkdir(parents=True, exist_ok=True)

    summary: dict[str, int] = {}
    for device, kind in DEVICES.items():
        measurements = KIND_MEASUREMENTS.get(kind, [])
        try:
            df = reader.read(device, measurements, start=start)
        except Exception as e:  # noqa: BLE001 — one bad device shouldn't abort the run
            log.warning("device read failed", device=device, error=str(e))
            continue
        if df.empty:
            log.warning("no data", device=device)
            continue
        path = out_dir / f"{device}.parquet"
        df.to_parquet(path)
        summary[device] = len(df)
        log.info("wrote snapshot", device=device, rows=len(df), path=str(path))

    log.info("ingest complete", devices=len(summary), total_rows=sum(summary.values()))
    return summary


def load_snapshot(device: str, data_dir: Path | None = None) -> pd.DataFrame:
    """Load a previously ingested device snapshot from `data/raw/sensors/`."""
    data_dir = data_dir or (settings.data_dir / "raw" / "sensors")
    return pd.read_parquet(data_dir / f"{device}.parquet")


def load_weather_snapshot(data_dir: Path | None = None) -> pd.DataFrame | None:
    """Load the most recent weather snapshot from `data/raw/weather/`, if any.

    Snapshots are named `weather_<start>_<end>.parquet`, so lexicographic order
    is chronological. Returns None when no snapshot exists (weather is optional
    for the model tracks — they run on sensors alone, just with fewer features).
    """
    weather_dir = (data_dir or (settings.data_dir / "raw")) / "weather"
    files = sorted(weather_dir.glob("weather_*.parquet"))
    if not files:
        return None
    return pd.read_parquet(files[-1])


def ingest_weather(days: int = 30, out_dir: Path | None = None) -> int:
    """Snapshot the last `days` of historical weather to `data/raw/weather/`.

    Uses the Open-Meteo archive at the configured vineyard coordinates. Returns
    the number of daily rows written. The archive lags ~5 days, so the window is
    [today-days, today].
    """
    out_dir = out_dir or (settings.data_dir / "raw" / "weather")
    out_dir.mkdir(parents=True, exist_ok=True)

    today = pd.Timestamp.utcnow().normalize()
    start = (today - pd.Timedelta(days=days)).strftime("%Y-%m-%d")
    end = today.strftime("%Y-%m-%d")

    df = fetch_historical(start, end)
    path = out_dir / f"weather_{start}_{end}.parquet"
    df.to_parquet(path)
    log.info("wrote weather snapshot", rows=len(df), path=str(path))
    return len(df)

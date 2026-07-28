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
from vine.d1_pipeline.validation import flag_out_of_range, gap_report, physical_range
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
    "pipe_pressure": ["pressure"],
}

# Engineering units carried into quality profiles. EM500-PP-4842 is omitted:
# its raw pressure encoding is known, but its physical unit is not yet verified.
KIND_UNITS: dict[str, dict[str, str]] = {
    "air": {"co2": "ppm", "humidity": "%", "temperature": "degC", "pressure": "hPa"},
}


def ingest_device(
    device: str,
    start: str,
    stop: str | None = None,
    out_dir: Path | None = None,
    reader: InfluxReader | None = None,
) -> pd.DataFrame:
    """Pull and snapshot one known device over a bounded interval.

    ``stop`` is required so profiling pulls cannot accidentally run unbounded.
    The returned frame carries source/provenance metadata in ``DataFrame.attrs``.
    """
    if device not in DEVICES:
        raise ValueError(f"Unknown device: {device}")
    if stop is None:
        raise ValueError("A stop bound is required for single-device ingestion")

    kind = DEVICES[device]
    reader = reader or InfluxReader()
    frame = reader.read(device, KIND_MEASUREMENTS[kind], start=start, stop=stop)
    frame.attrs.update(
        {
            "source": "influxdb",
            "device": device,
            "device_kind": kind,
            "query_start": start,
            "query_stop": stop,
            "units": KIND_UNITS.get(kind, {}),
        }
    )
    if not frame.empty and out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(out_dir / f"{device}.parquet")
    return frame


def quality_profile(frame: pd.DataFrame, *, freq: str = "1h") -> pd.DataFrame:
    """Summarize provenance, completeness, and safe range checks by column.

    A column with an unknown unit reports no physical-range count. This blocks
    downstream event semantics until the unit is verified rather than guessed.
    """
    units: dict[str, str] = frame.attrs.get("units", {})
    gaps = gap_report(frame, freq=freq)
    flags = flag_out_of_range(frame, units=units)
    rows: list[dict[str, object]] = []
    for column in frame.select_dtypes(include="number").columns:
        unit = units.get(column)
        semantic_ready = physical_range(column, unit) is not None
        rows.append(
            {
                "device": frame.attrs.get("device"),
                "source": frame.attrs.get("source"),
                "query_start": frame.attrs.get("query_start"),
                "query_stop": frame.attrs.get("query_stop"),
                "column": column,
                "unit": unit,
                "observations": int(frame[column].notna().sum()),
                "missing_bins": int(gaps.get(column, 0)),
                "out_of_range": int(flags[column].sum()) if semantic_ready else None,
                "physical_semantics": semantic_ready,
            }
        )
    return pd.DataFrame(rows)


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

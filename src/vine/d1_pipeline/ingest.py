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

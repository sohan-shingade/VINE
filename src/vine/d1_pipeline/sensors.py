"""Regularize sensor time-series after ingestion.

The **live** sensor source is InfluxDB (see `vine.d1_pipeline.influx`); this module
takes those (or any CSV export / DVC snapshot) tidy frames and regularizes them:
resample to a fixed grid and flag gaps for downstream imputation (validation.py).
Readings are irregular and gappy (sensor failures, connectivity drops).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

SENSOR_COLUMNS = ["soil_moisture", "temperature", "co2", "humidity"]


def read_sensor_csv(path: str | Path) -> pd.DataFrame:
    """Read one sensor CSV into a tidy frame indexed by UTC timestamp.

    Expected columns: timestamp, sensor_id, + any of SENSOR_COLUMNS.
    """
    df = pd.read_csv(path, parse_dates=["timestamp"])
    return df.set_index("timestamp").sort_index()


def resample(df: pd.DataFrame, freq: str = "1h") -> pd.DataFrame:
    """Resample to a regular grid (default hourly), mean-aggregating per bin.

    Leaves NaNs where no reading exists — imputation is an explicit, separate
    step so gaps stay visible to validation.
    """
    return df.resample(freq).mean(numeric_only=True)

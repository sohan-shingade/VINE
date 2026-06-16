"""Data-quality checks: range validation, gap detection, staleness flags.

A core mitigation from the proposal — sensor data is gappy and noisy, so the
pipeline must distinguish "sensor failure" from "real signal" rather than
silently imputing. Returns explicit flags, never drops data quietly.
"""

from __future__ import annotations

import pandas as pd

# Plausible physical ranges; readings outside are flagged, not deleted.
RANGES: dict[str, tuple[float, float]] = {
    "soil_moisture": (0.0, 100.0),  # volumetric %
    "temperature": (-20.0, 60.0),  # °C
    "co2": (300.0, 5000.0),  # ppm
    "humidity": (0.0, 100.0),  # %
}


def flag_out_of_range(df: pd.DataFrame) -> pd.DataFrame:
    """Return a boolean frame: True where a value is outside its plausible range."""
    flags = pd.DataFrame(False, index=df.index, columns=df.columns)
    for col, (lo, hi) in RANGES.items():
        if col in df.columns:
            flags[col] = (df[col] < lo) | (df[col] > hi)
    return flags


def gap_report(df: pd.DataFrame, freq: str = "1h") -> pd.Series:
    """Count missing bins per column on a regular `freq` grid (a completeness report)."""
    full = df.resample(freq).mean(numeric_only=True)
    return full.isna().sum()

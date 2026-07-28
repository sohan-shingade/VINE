"""Data-quality checks: range validation, gap detection, staleness flags.

A core mitigation from the proposal — sensor data is gappy and noisy, so the
pipeline must distinguish "sensor failure" from "real signal" rather than
silently imputing. Returns explicit flags, never drops data quietly.
"""

from __future__ import annotations

from collections.abc import Mapping

import pandas as pd

# Plausible physical ranges; readings outside are flagged, not deleted.
RANGES: dict[str, tuple[float, float]] = {
    "soil_moisture": (0.0, 100.0),  # volumetric %
    "temperature": (-20.0, 60.0),  # °C
    "co2": (300.0, 5000.0),  # ppm
    "humidity": (0.0, 100.0),  # %
    "pressure": (800.0, 1100.0),  # hPa, barometric sensors only
}

# A physical range is valid only when the engineering unit is known. Raw values
# such as pipe_pressure_raw intentionally have no entry and receive no semantics.
UNITS: dict[str, str] = {
    "soil_moisture": "%",
    "temperature": "degC",
    "co2": "ppm",
    "humidity": "%",
    "pressure": "hPa",
}


def physical_range(column: str, unit: str | None) -> tuple[float, float] | None:
    """Return a column's physical range only when its unit is known and matches."""
    if unit is None or UNITS.get(column) != unit:
        return None
    return RANGES.get(column)


def flag_out_of_range(
    df: pd.DataFrame,
    units: Mapping[str, str | None] | None = None,
) -> pd.DataFrame:
    """Return flags for values outside ranges whose engineering unit is known.

    Omitting ``units`` preserves the original behavior for established columns.
    When units are supplied, unknown or mismatched units block physical semantics:
    those columns remain unflagged rather than receiving a guessed interpretation.
    """
    flags = pd.DataFrame(False, index=df.index, columns=df.columns)
    for col in df.columns:
        bounds = RANGES.get(col) if units is None else physical_range(col, units.get(col))
        if bounds is not None:
            lo, hi = bounds
            flags[col] = (df[col] < lo) | (df[col] > hi)
    return flags


def gap_report(df: pd.DataFrame, freq: str = "1h") -> pd.Series:
    """Count missing bins per column on a regular `freq` grid (a completeness report)."""
    full = df.resample(freq).mean(numeric_only=True)
    return full.isna().sum()


def flag_gaps(df: pd.DataFrame) -> pd.DataFrame:
    """Return a boolean frame: True where a value is missing (a gap).

    Run on an already-regularized grid (see `sensors.resample`): a NaN there means
    "no reading in this bin," which we flag rather than silently impute.
    """
    return df.isna()

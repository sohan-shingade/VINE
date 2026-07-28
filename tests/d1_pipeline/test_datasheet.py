"""Tests for offline D1 datasheet summaries."""

from pathlib import Path

import pandas as pd
import pytest

from vine.d1_pipeline.datasheet import (
    dvc_snapshot_manifest,
    read_imagery_inventory,
    sensor_coverage,
    weather_coverage,
    weekly_missingness,
)


def _frame(values: list[float], start: str = "2026-01-01") -> pd.DataFrame:
    return pd.DataFrame(
        {"soil_water": values},
        index=pd.date_range(start, periods=len(values), freq="1h", tz="UTC"),
    )


def test_sensor_coverage_preserves_gaps_and_cadence():
    table = sensor_coverage({"b": _frame([1.0, float("nan"), 3.0])})
    row = table.iloc[0]
    assert row.device == "b"
    assert row.raw_rows == 2
    assert row.expected_bins == 3
    assert row.missing_bins == 1
    assert row.missing_pct == pytest.approx(100 / 3)
    assert row.longest_gap_bins == 1
    assert row.median_cadence_min == 60.0


def test_weekly_missingness_keeps_fully_missing_week():
    frame = _frame([1.0] * (24 * 7) + [float("nan")] * (24 * 7))
    table = weekly_missingness({"probe": frame}, channels={"probe": "soil_water"})
    assert table.missing_fraction.max() == 1.0
    assert table.missing_fraction.min() == 0.0


def test_weather_coverage_reports_each_driver():
    index = pd.date_range("2026-01-01", periods=72, freq="1h", tz="UTC")
    weather = pd.DataFrame(
        {"precip_mm": [0.0, 1.0], "et0_mm": [1.0, float("nan")]},
        index=pd.date_range("2026-01-01", periods=2, freq="1D"),
    )
    table = weather_coverage(index, weather).set_index("channel")
    assert table.loc["precip_mm", "covered_days"] == 2
    assert table.loc["et0_mm", "covered_days"] == 1
    assert table.loc["precip_mm", "expected_days"] == 3


def test_dvc_snapshot_manifest(tmp_path: Path):
    pointer = tmp_path / "sensors.dvc"
    pointer.write_text("outs:\n- md5: abc.dir\n  size: 12\n  nfiles: 3\n  path: sensors\n")
    row = dvc_snapshot_manifest([pointer]).iloc[0]
    assert row.md5 == "abc.dir"
    assert row.nfiles == 3


def test_imagery_inventory_requires_stable_schema(tmp_path: Path):
    path = tmp_path / "inventory.parquet"
    pd.DataFrame({"block_id": ["H5"]}).to_parquet(path)
    with pytest.raises(ValueError, match="missing columns"):
        read_imagery_inventory(path)

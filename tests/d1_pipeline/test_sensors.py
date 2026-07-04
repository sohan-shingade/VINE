"""Sensor regularization tests — resample to a grid, leave gaps visible."""

import pandas as pd

from vine.d1_pipeline import sensors


def test_resample_means_within_bin_and_leaves_gaps():
    idx = pd.to_datetime(["2025-08-01T00:00", "2025-08-01T00:30", "2025-08-01T02:00"])
    df = pd.DataFrame({"soil_water": [10.0, 20.0, 40.0]}, index=idx)
    out = sensors.resample(df, "1h")
    assert out.loc["2025-08-01T00:00", "soil_water"] == 15.0  # mean(10, 20)
    assert pd.isna(out.loc["2025-08-01T01:00", "soil_water"])  # gap, NOT imputed
    assert out.loc["2025-08-01T02:00", "soil_water"] == 40.0


def test_read_sensor_csv_sorts_by_time(tmp_path):
    p = tmp_path / "s.csv"
    p.write_text("timestamp,sensor_id,soil_moisture\n2025-08-01T01:00,A,5\n2025-08-01T00:00,A,3\n")
    df = sensors.read_sensor_csv(p)
    assert df.index.is_monotonic_increasing
    assert list(df["soil_moisture"]) == [3, 5]

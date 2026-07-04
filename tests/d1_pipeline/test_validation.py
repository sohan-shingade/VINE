"""Data-quality tests — range flags, gap flags, completeness report."""

import pandas as pd

from vine.d1_pipeline import validation


def test_flag_out_of_range():
    df = pd.DataFrame({"soil_moisture": [50.0, 150.0, -1.0], "temperature": [20.0, 20.0, 20.0]})
    flags = validation.flag_out_of_range(df)
    assert list(flags["soil_moisture"]) == [False, True, True]  # 150 and -1 are impossible
    assert not flags["temperature"].any()


def test_flag_gaps_marks_missing():
    df = pd.DataFrame({"x": [1.0, None, 3.0]})
    assert list(validation.flag_gaps(df)["x"]) == [False, True, False]


def test_gap_report_counts_missing_bins():
    idx = pd.to_datetime(["2025-08-01T00:00", "2025-08-01T02:00"])
    df = pd.DataFrame({"x": [1.0, 2.0]}, index=idx)
    rep = validation.gap_report(df, "1h")
    assert rep["x"] == 1  # the 01:00 bin is missing

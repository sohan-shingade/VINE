"""Data-quality tests — range flags, gap flags, completeness report."""

import pandas as pd

from vine.d1_pipeline import validation


def test_flag_out_of_range():
    df = pd.DataFrame({"soil_moisture": [50.0, 150.0, -1.0], "temperature": [20.0, 20.0, 20.0]})
    flags = validation.flag_out_of_range(df)
    assert list(flags["soil_moisture"]) == [False, True, True]  # 150 and -1 are impossible
    assert not flags["temperature"].any()


def test_unknown_unit_blocks_physical_range_semantics():
    frame = pd.DataFrame({"pipe_pressure_raw": [-1_000_000.0], "pressure": [2_000.0]})
    flags = validation.flag_out_of_range(
        frame,
        units={"pipe_pressure_raw": None, "pressure": "unknown"},
    )

    assert not flags.any().any()
    assert validation.physical_range("pipe_pressure_raw", None) is None
    assert validation.physical_range("pressure", "unknown") is None


def test_known_pressure_unit_enables_barometric_range():
    frame = pd.DataFrame({"pressure": [1013.0, 2_000.0]})
    flags = validation.flag_out_of_range(frame, units={"pressure": "hPa"})
    assert list(flags["pressure"]) == [False, True]


def test_flag_gaps_marks_missing():
    df = pd.DataFrame({"x": [1.0, None, 3.0]})
    assert list(validation.flag_gaps(df)["x"]) == [False, True, False]


def test_gap_report_counts_missing_bins():
    idx = pd.to_datetime(["2025-08-01T00:00", "2025-08-01T02:00"])
    df = pd.DataFrame({"x": [1.0, 2.0]}, index=idx)
    rep = validation.gap_report(df, "1h")
    assert rep["x"] == 1  # the 01:00 bin is missing

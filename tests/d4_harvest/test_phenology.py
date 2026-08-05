"""GDD phenology tests — pure math, band crossings, and gap handling (no network)."""

import pandas as pd
import pytest

from vine.d4_harvest.phenology import (
    GddExplorationConfig,
    PhenologyBand,
    Season,
    band_crossings,
    daily_gdd,
    explore_seasons,
    gdd_trajectory,
    winkler_region,
)


def _weather(dates, tmax, tmin):
    idx = pd.DatetimeIndex(pd.to_datetime(dates), name="date")
    return pd.DataFrame({"temp_max_c": tmax, "temp_min_c": tmin}, index=idx)


# --- pure GDD math -------------------------------------------------------


def test_daily_gdd_known_values():
    w = _weather(["2025-04-01", "2025-04-02", "2025-04-03"], [20.0, 12.0, 30.0], [10.0, 4.0, 10.0])
    gdd = daily_gdd(w["temp_max_c"], w["temp_min_c"], base=10.0)
    # mean 15 -> 5; mean 8 -> below base, clipped to 0; mean 20 -> 10
    assert list(gdd) == [5.0, 0.0, 10.0]


def test_daily_gdd_base_is_configurable():
    w = _weather(["2025-04-01"], [20.0], [10.0])
    assert daily_gdd(w["temp_max_c"], w["temp_min_c"], base=5.0).iloc[0] == 10.0


def test_daily_gdd_upper_cap_clips_both_temps():
    w = _weather(["2025-04-01"], [40.0], [20.0])
    uncapped = daily_gdd(w["temp_max_c"], w["temp_min_c"], base=10.0).iloc[0]
    capped = daily_gdd(w["temp_max_c"], w["temp_min_c"], base=10.0, upper_cap=30.0).iloc[0]
    assert uncapped == 20.0  # mean 30 - 10
    assert capped == 15.0  # mean(30, 20) - 10


def test_daily_gdd_missing_day_is_nan_not_zero():
    w = _weather(["2025-04-01", "2025-04-02"], [20.0, float("nan")], [10.0, 10.0])
    gdd = daily_gdd(w["temp_max_c"], w["temp_min_c"])
    assert gdd.iloc[0] == 5.0
    assert pd.isna(gdd.iloc[1])


# --- trajectory ----------------------------------------------------------


def test_gdd_trajectory_accumulates_and_flags_complete_days():
    w = _weather(["2025-04-01", "2025-04-02", "2025-04-03"], [20.0, 22.0, 24.0], [10.0, 10.0, 10.0])
    traj = gdd_trajectory(w, start="2025-04-01", end="2025-04-03")
    assert list(traj["gdd_day"]) == [5.0, 6.0, 7.0]
    assert list(traj["gdd_cumulative"]) == [5.0, 11.0, 18.0]
    assert not traj["missing_day"].any()
    assert list(traj["missing_days_to_date"]) == [0, 0, 0]


def test_gdd_trajectory_flags_absent_days_without_imputing():
    # 2025-04-02 is absent from the source frame entirely.
    w = _weather(["2025-04-01", "2025-04-03"], [20.0, 24.0], [10.0, 10.0])
    traj = gdd_trajectory(w, start="2025-04-01", end="2025-04-03")
    assert len(traj) == 3  # reindexed onto a complete daily grid
    assert list(traj["missing_day"]) == [False, True, False]
    assert pd.isna(traj["gdd_day"].iloc[1])
    # the gap is NaN in the cumulative curve too, and contributes nothing after:
    # the trajectory is a lower bound, never filled in
    cumulative = list(traj["gdd_cumulative"])
    assert cumulative[0] == 5.0
    assert pd.isna(cumulative[1])
    assert cumulative[2] == 12.0
    assert list(traj["missing_days_to_date"]) == [0, 1, 1]


def test_gdd_trajectory_truncates_to_last_available_day():
    w = _weather(["2025-04-01", "2025-04-02"], [20.0, 22.0], [10.0, 10.0])
    traj = gdd_trajectory(w, start="2025-04-01", end="2025-10-31")
    assert traj.index.max() == pd.Timestamp("2025-04-02")


def test_gdd_trajectory_requires_temperature_columns():
    frame = pd.DataFrame({"precip_mm": [0.0]}, index=pd.DatetimeIndex(["2025-04-01"], name="date"))
    with pytest.raises(ValueError, match="temp_max_c"):
        gdd_trajectory(frame, start="2025-04-01", end="2025-04-01")


# --- band crossings ------------------------------------------------------


def _ten_day_trajectory():
    dates = pd.date_range("2025-04-01", periods=10, freq="D")
    w = _weather(dates, [30.0] * 10, [10.0] * 10)  # 10 GDD/day
    return gdd_trajectory(w, start="2025-04-01", end="2025-04-10")


def test_band_crossings_first_date_at_or_above_threshold():
    bands = [PhenologyBand(name="b", gdd_start=30.0, gdd_end=100.0)]
    cross = band_crossings(_ten_day_trajectory(), bands)
    assert list(cross["edge"]) == ["start", "end"]
    start_row = cross.iloc[0]
    assert start_row["crossed_date"] == pd.Timestamp("2025-04-03")  # cum 30 on day 3
    assert start_row["day_of_season"] == 3
    assert start_row["gdd_cumulative"] == 30.0
    assert cross.iloc[1]["crossed_date"] == pd.Timestamp("2025-04-10")  # cum 100 on day 10


def test_band_crossings_never_reached_is_nat():
    bands = [PhenologyBand(name="veraison", gdd_start=1100.0)]
    cross = band_crossings(_ten_day_trajectory(), bands)
    assert pd.isna(cross.iloc[0]["crossed_date"])
    assert cross.iloc[0]["day_of_season"] is None


def test_band_crossings_marks_incomplete_when_days_are_missing():
    w = _weather(["2025-04-01", "2025-04-03", "2025-04-04"], [30.0, 30.0, 30.0], [10.0, 10.0, 10.0])
    traj = gdd_trajectory(w, start="2025-04-01", end="2025-04-04")
    cross = band_crossings(traj, [PhenologyBand(name="b", gdd_start=25.0)])
    row = cross.iloc[0]
    assert row["crossed_date"] == pd.Timestamp("2025-04-04")
    assert row["missing_days_before"] == 1
    assert bool(row["complete"]) is False  # the real crossing may be earlier


def test_band_rejects_inverted_span():
    with pytest.raises(ValueError, match="gdd_end"):
        PhenologyBand(name="bad", gdd_start=200.0, gdd_end=100.0)


# --- Winkler regions + season wiring ------------------------------------


def test_winkler_region_bounds():
    assert winkler_region(1200.0) == "Region I"
    assert winkler_region(1389.0) == "Region II"
    assert winkler_region(5000.0) == "Region V"


def test_explore_seasons_returns_per_season_tables():
    dates = pd.date_range("2025-04-01", "2026-08-04", freq="D")
    w = _weather(dates, [30.0] * len(dates), [10.0] * len(dates))
    cfg = GddExplorationConfig(
        seasons=[
            Season(label="2025", start="2025-04-01", end="2025-04-10"),
            Season(label="2026", start="2026-04-01", end="2026-04-05"),
        ],
        bands=[PhenologyBand(name="b", gdd_start=30.0)],
    )
    traj, cross = explore_seasons(w, cfg)
    assert set(traj["season"]) == {"2025", "2026"}
    assert len(traj) == 15
    assert list(cross["season"]) == ["2025", "2026"]
    assert cross.iloc[0]["season_gdd_total"] == 100.0
    assert cross.iloc[0]["season_missing_days"] == 0
    assert bool(cross.iloc[0]["season_partial"]) is False


def test_explore_seasons_marks_partial_season_unclassifiable():
    dates = pd.date_range("2026-04-01", "2026-04-20", freq="D")
    w = _weather(dates, [30.0] * len(dates), [10.0] * len(dates))
    cfg = GddExplorationConfig(
        seasons=[Season(label="2026", start="2026-04-01", end="2026-10-31")],
        bands=[PhenologyBand(name="b", gdd_start=30.0)],
    )
    _, cross = explore_seasons(w, cfg)
    assert bool(cross.iloc[0]["season_partial"]) is True
    assert cross.iloc[0]["winkler_region"] == "n/a (partial season)"

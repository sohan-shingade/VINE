"""Sensor-path assembly tests — build_sensor_features + attach_weather."""

import pandas as pd

from vine.d1_pipeline import pipeline


def test_build_sensor_features_flags_gaps_and_adds_features():
    idx = pd.to_datetime(["2025-08-01T00:00", "2025-08-01T00:30", "2025-08-01T02:00"])
    raw = pd.DataFrame({"soil_water": [10.0, 20.0, 40.0]}, index=idx)
    out = pipeline.build_sensor_features(
        raw, ["soil_water"], freq="1h", rolling_windows=("1h",), lags=(1,)
    )
    # grid bins 00:00, 01:00 (gap), 02:00
    assert out["soil_water_is_gap"].tolist() == [False, True, False]
    assert "soil_water_mean_1h" in out.columns
    assert "soil_water_lag_1" in out.columns
    assert "soil_water_out_of_range" in out.columns


def test_build_sensor_features_coerces_string_values():
    # InfluxDB pivots can return numeric readings as strings
    idx = pd.date_range("2025-08-01", periods=3, freq="1h")
    raw = pd.DataFrame({"soil_water": ["10.0", "20.0", "bad"]}, index=idx)
    out = pipeline.build_sensor_features(
        raw, ["soil_water"], freq="1h", rolling_windows=("1h",), lags=(1,)
    )
    assert out["soil_water_is_gap"].tolist() == [False, False, True]  # "bad" -> gap


def test_build_sensor_features_defaults_to_all_columns():
    idx = pd.date_range("2025-08-01", periods=2, freq="1h")
    raw = pd.DataFrame({"a": [1.0, 2.0], "b": [3.0, 4.0]}, index=idx)
    out = pipeline.build_sensor_features(raw, freq="1h", rolling_windows=("1h",), lags=(1,))
    assert "a_is_gap" in out.columns and "b_is_gap" in out.columns


def test_attach_weather_broadcasts_daily_and_computes_gdd():
    fidx = pd.date_range("2025-08-01", periods=48, freq="1h")
    frame = pd.DataFrame({"x": range(48)}, index=fidx, dtype=float)
    widx = pd.to_datetime(["2025-08-01", "2025-08-02"])
    weather = pd.DataFrame(
        {
            "temp_max_c": [30.0, 32.0],
            "temp_min_c": [10.0, 12.0],
            "precip_mm": [0.0, 1.0],
            "et0_mm": [5.0, 6.0],
        },
        index=widx,
    )
    out = pipeline.attach_weather(frame, weather)
    # daily values forward-filled onto the hourly grid
    assert out.loc["2025-08-01T05:00", "temp_max_c"] == 30.0
    assert out.loc["2025-08-02T05:00", "temp_max_c"] == 32.0
    # GDD: day1 mean=20 -> +10; day2 mean=22 -> +12 -> cumulative 22
    assert out.loc["2025-08-01T05:00", "gdd"] == 10.0
    assert out.loc["2025-08-02T05:00", "gdd"] == 22.0


def test_add_lead_time_features_sums_forward_and_names_columns():
    idx = pd.date_range("2026-01-01", periods=6, freq="1h")
    # Daily totals (arbitrary, not required to be constant per day for this
    # unit test — the function just treats each row as `value / 24` mm/h).
    precip_mm = [0.0, 24.0, 48.0, 72.0, 96.0, 120.0]
    frame = pd.DataFrame({"precip_mm": precip_mm}, index=idx)
    out = pipeline.add_lead_time_features(frame, [2])

    assert "precip_next_2h" in out.columns
    assert "et0_next_2h" not in out.columns  # et0_mm absent from the input -> skipped

    rate = [v / 24.0 for v in precip_mm]  # [0, 1, 2, 3, 4, 5]
    # row s covers (s, s+2]: sum of rate[s+1] + rate[s+2]
    expected = [rate[1] + rate[2], rate[2] + rate[3], rate[3] + rate[4], rate[4] + rate[5]]
    got = out["precip_next_2h"].tolist()
    assert got[:4] == expected
    assert pd.isna(got[4]) and pd.isna(got[5])  # window runs past the end of the frame


def test_attach_weather_reconciles_tz_aware_frame():
    # real sensor snapshots are tz-aware (UTC); weather dates are tz-naive
    fidx = pd.date_range("2025-08-01", periods=24, freq="1h", tz="UTC")
    frame = pd.DataFrame({"x": range(24)}, index=fidx, dtype=float)
    weather = pd.DataFrame(
        {"temp_max_c": [30.0], "temp_min_c": [10.0]},
        index=pd.to_datetime(["2025-08-01"]),  # tz-naive
    )
    out = pipeline.attach_weather(frame, weather)
    assert out.loc["2025-08-01T05:00", "temp_max_c"] == 30.0
    assert out["temp_max_c"].notna().all()

"""Rise-event detection and rain attribution (D2 inferred irrigation events)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from vine.d2_irrigation.events import attribute_rain, detect_rise_events


def _hourly(values: list[float], start: str = "2026-03-01") -> pd.Series:
    idx = pd.date_range(start, periods=len(values), freq="1h", tz="UTC")
    return pd.Series(values, index=idx, dtype=float)


def test_clean_jump_detected_with_correct_magnitude():
    flat = [25.0] * 10
    rise = [25.5, 26.2, 27.0]  # 3 rising hours, cumulative +2.0
    series = _hourly(flat + rise + [26.9] * 10)
    events = detect_rise_events(series, min_jump=1.0)
    assert len(events) == 1
    ev = events.iloc[0]
    assert ev.trough == 25.0
    assert ev.peak == 27.0
    assert np.isclose(ev.jump, 2.0)
    assert ev.span_h == 3
    assert ev.start == series.index[9]
    assert ev.end == series.index[12]


def test_slow_smooth_drift_not_detected():
    # +0.05/h for 48 h accumulates 2.4 units but far exceeds max_span_h.
    drift = 25.0 + 0.05 * np.arange(48)
    series = _hourly([25.0] * 5 + list(drift) + [drift[-1]] * 5)
    events = detect_rise_events(series, min_jump=1.0, max_span_h=12)
    assert events.empty


def test_jump_adjacent_to_nan_gap_excluded():
    flat = [25.0] * 10
    rise = [25.5, 26.2, 27.0]
    tail = [26.9] * 10
    clean = _hourly(flat + rise + tail)
    assert len(detect_rise_events(clean, min_jump=1.0)) == 1
    # NaN immediately after the peak: the same rise must be excluded.
    gapped = clean.copy()
    gapped.iloc[13] = np.nan
    assert detect_rise_events(gapped, min_jump=1.0).empty
    # NaN immediately before the trough: excluded too.
    gapped = clean.copy()
    gapped.iloc[8] = np.nan
    assert detect_rise_events(gapped, min_jump=1.0).empty


def test_rise_at_series_edge_excluded():
    # A rise starting at the first observed hour has no pre-trough context.
    series = _hourly([25.0, 26.0, 27.0] + [27.0] * 10)
    assert detect_rise_events(series, min_jump=1.0).empty


def test_rain_day_attributed_to_rain_dry_day_to_irrigation():
    flat = [25.0] * 10
    rise = [25.5, 26.2, 27.0]
    series = _hourly(flat + rise + [26.9] * 10, start="2026-03-01")
    events = detect_rise_events(series, min_jump=1.0)
    days = pd.date_range("2026-02-27", periods=6, freq="1D")

    dry = pd.Series(0.0, index=days)
    assert attribute_rain(events, dry)["attribution"].tolist() == ["irrigation"]

    rain_same_day = dry.copy()
    rain_same_day["2026-03-01"] = 5.0
    assert attribute_rain(events, rain_same_day)["attribution"].tolist() == ["rain"]

    rain_day_before = dry.copy()
    rain_day_before["2026-02-28"] = 5.0
    assert attribute_rain(events, rain_day_before)["attribution"].tolist() == ["rain"]

    below_threshold = dry.copy()
    below_threshold["2026-03-01"] = 0.4
    assert attribute_rain(events, below_threshold)["attribution"].tolist() == ["irrigation"]


def test_attribute_rain_empty_events():
    empty = detect_rise_events(_hourly([25.0] * 10))
    out = attribute_rain(empty, pd.Series(dtype=float))
    assert out.empty
    assert "attribution" in out.columns


def test_detection_is_deterministic():
    rng = np.random.default_rng(0)
    noise = 25.0 + np.cumsum(rng.normal(0, 0.1, 500))
    noise[200:204] += np.array([1.0, 2.0, 3.0, 3.0])
    series = _hourly(list(noise))
    precip = pd.Series(0.0, index=pd.date_range("2026-02-28", periods=30, freq="1D"))
    first = attribute_rain(detect_rise_events(series), precip)
    second = attribute_rain(detect_rise_events(series), precip)
    pd.testing.assert_frame_equal(first, second)

"""Infer irrigation events from soil-moisture rises (D2, exploratory).

During the dry season soil moisture only rises when water arrives, from rain
or from irrigation. Given an hourly soil-moisture series on a regular grid,
`detect_rise_events` finds sharp sustained rises, and `attribute_rain` labels
each one `rain` or `irrigation` using a daily precipitation series. Events
that coincide with recorded rain are rain; the rest are inferred irrigation.

Pure pandas, no I/O. The runner `scripts/d2_irrigation_events.py` feeds it the
pinned snapshots and writes the event catalog. The catalog is exploratory and
unvalidated: jumps are in raw sensor units and the events are candidates for
the mentor to check against real irrigation logs.
"""

from __future__ import annotations

import pandas as pd

EVENT_COLUMNS = ["start", "end", "trough", "peak", "jump", "span_h"]


def detect_rise_events(
    series: pd.Series,
    *,
    min_jump: float = 0.5,
    max_span_h: int = 12,
    rise_tol: float = 0.0,
) -> pd.DataFrame:
    """Detect sharp sustained rises in an hourly soil-moisture series.

    A rise event is a maximal run of consecutive hours whose hourly increase
    exceeds `rise_tol`, kept when the cumulative rise (peak minus trough) is
    at least `min_jump` and the run spans at most `max_span_h` hours. Slow
    smooth drift fails one of the two: either each hourly step is below
    `rise_tol`, or the run takes longer than `max_span_h` to accumulate
    `min_jump`.

    Gap rule: the series must be on a regular grid with gaps marked as NaN.
    An event is dropped if any hour from one hour before its trough to one
    hour after its peak is NaN or falls outside the series. A rise that spans
    or abuts a data gap can be an artifact of the gap and is never reported.

    Args:
        series: hourly soil moisture on a regular grid, NaN where missing.
        min_jump: minimum cumulative rise (sensor units) to count as an event.
        max_span_h: maximum event length in hours (trough to peak).
        rise_tol: minimum hourly increase for an hour to count as rising.

    Returns:
        DataFrame with one row per event: `start` (trough time), `end` (peak
        time), `trough`, `peak`, `jump` (peak minus trough), `span_h` (hours
        from trough to peak). Sorted by `start`.
    """
    diff = series.diff()
    rising = (diff > rise_tol).to_numpy()
    observed = series.notna().to_numpy()
    values = series.to_numpy()

    events: list[tuple] = []
    n = len(series)
    i = 0
    while i < n:
        if not rising[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and rising[j + 1]:
            j += 1
        t0, t1 = i - 1, j  # trough index, peak index
        jump = values[t1] - values[t0]
        clear_of_gaps = t0 - 1 >= 0 and t1 + 1 < n and observed[t0 - 1 : t1 + 2].all()
        if clear_of_gaps and jump >= min_jump and t1 - t0 <= max_span_h:
            events.append(
                (series.index[t0], series.index[t1], values[t0], values[t1], jump, t1 - t0)
            )
        i = j + 1
    return pd.DataFrame(events, columns=EVENT_COLUMNS)


def attribute_rain(
    events: pd.DataFrame,
    precip_daily: pd.Series,
    *,
    rain_mm: float = 1.0,
) -> pd.DataFrame:
    """Attribute each rise event to rain or irrigation.

    An event is `rain` when daily precipitation on the event's start day or
    the previous day is at least `rain_mm`. Everything else is `irrigation`.
    Days absent from `precip_daily` compare as dry; callers should verify the
    precipitation series covers the sensor window.

    Args:
        events: events frame from `detect_rise_events`.
        precip_daily: daily precipitation in mm, indexed by date (tz-naive).
        rain_mm: precipitation threshold in mm for rain attribution.

    Returns:
        Copy of `events` with an added `attribution` column.
    """
    out = events.copy()
    if out.empty:
        out["attribution"] = pd.Series(dtype=object)
        return out

    starts = pd.DatetimeIndex(out["start"])
    if starts.tz is not None:
        starts = starts.tz_convert(None)
    days = starts.normalize()
    day_precip = precip_daily.reindex(days).to_numpy()
    prev_precip = precip_daily.reindex(days - pd.Timedelta(days=1)).to_numpy()
    rainy = (day_precip >= rain_mm) | (prev_precip >= rain_mm)
    out["attribution"] = ["rain" if r else "irrigation" for r in rainy]
    return out

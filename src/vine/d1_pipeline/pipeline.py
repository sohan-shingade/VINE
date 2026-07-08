"""Assemble the processed sensor feature table — the D1 sensor path.

Ties the loose steps together so the model tracks consume one model-ready frame
instead of re-implementing ingestion:

    raw tidy frame -> regularize (fixed grid) -> quality flags (gaps + range)
                   -> features (rolling, lag) -> (optionally) join weather + GDD

The raw frame comes from an InfluxDB snapshot (`ingest.load_snapshot`) or any
CSV/DVC snapshot. Pure pandas; weather is the only network input and is passed
in already-fetched (see `weather.fetch_historical`).
"""

from __future__ import annotations

import pandas as pd

from vine.d1_pipeline import features, sensors, validation


def build_sensor_features(
    raw: pd.DataFrame,
    value_cols: list[str] | None = None,
    *,
    freq: str = "1h",
    rolling_windows: tuple[str, ...] = ("1h", "6h", "24h"),
    lags: tuple[int, ...] = (1, 6, 24),
) -> pd.DataFrame:
    """Build the model-ready feature frame for one device's sensor readings.

    Regularizes to `freq`, appends rolling/lag features per value column, and
    adds explicit `<col>_is_gap` / `<col>_out_of_range` quality flags. Gaps are
    flagged, never imputed — downstream models decide how to handle them.

    Args:
        raw: tidy frame indexed by UTC timestamp (irregular, possibly gappy).
        value_cols: columns to featurize; defaults to all numeric columns.
        freq: regular-grid frequency (pandas offset alias).
        rolling_windows: time windows for rolling mean/std.
        lags: lags (in grid rows) for lag features.
    """
    # Coerce candidate value columns to numeric first — snapshots can carry
    # numeric readings as strings; non-numeric becomes NaN (a flagged gap).
    work = raw.copy()
    candidates = value_cols if value_cols is not None else list(work.columns)
    for c in candidates:
        if c in work.columns and c != "device_name":
            work[c] = pd.to_numeric(work[c], errors="coerce")

    grid = sensors.resample(work, freq)
    if value_cols is None:
        value_cols = list(grid.columns)
    cols = [c for c in value_cols if c in grid.columns]

    out = grid[cols].copy()
    for col in cols:
        out = features.rolling_features(out, col, rolling_windows)
        out = features.lag_features(out, col, lags)

    gaps = validation.flag_gaps(grid[cols])
    oor = validation.flag_out_of_range(grid[cols])
    for col in cols:
        out[f"{col}_is_gap"] = gaps[col]
        out[f"{col}_out_of_range"] = oor[col]
    return out


def attach_weather(
    frame: pd.DataFrame,
    weather_daily: pd.DataFrame,
    *,
    gdd_base: float = 10.0,
) -> pd.DataFrame:
    """Broadcast daily weather onto a (sub-)daily feature frame and add GDD.

    Daily weather (from `weather.fetch_historical`) is forward-filled onto the
    frame's finer-grained index, so each row carries the most recent day's
    weather. Cumulative growing degree-days are computed from daily mean temp
    when `temp_max_c`/`temp_min_c` are present.
    """
    w = weather_daily.copy()
    if "temp_max_c" in w.columns and "temp_min_c" in w.columns:
        w["temp_mean_c"] = (w["temp_max_c"] + w["temp_min_c"]) / 2.0
        w["gdd"] = features.growing_degree_days(w["temp_mean_c"], base=gdd_base)

    # Reconcile timezones: real sensor snapshots are tz-aware (UTC); the weather
    # archive returns tz-naive dates. Align weather to the frame before joining.
    ftz = getattr(frame.index, "tz", None)
    wtz = getattr(w.index, "tz", None)
    if ftz is not None and wtz is None:
        w.index = w.index.tz_localize(ftz)
    elif ftz is None and wtz is not None:
        w.index = w.index.tz_localize(None)
    elif ftz is not None and wtz is not None and str(ftz) != str(wtz):
        w.index = w.index.tz_convert(ftz)

    # as-of forward-fill: reindex onto the union, ffill, then back to frame index
    broadcast = w.reindex(frame.index.union(w.index)).sort_index().ffill().reindex(frame.index)
    return frame.join(broadcast, how="left")


def add_lead_time_features(
    frame: pd.DataFrame,
    horizons_h: list[int],
    cols: tuple[str, ...] = ("precip_mm", "et0_mm"),
) -> pd.DataFrame:
    """Add "what will the weather DO next" features — D2's lead-time rung.

    `attach_weather` forward-fills each day's total onto every hourly row of
    that day, so `frame[col]` is constant within a day. This turns that daily
    total into an hourly rate (`col / 24`) and sums it forward over the next
    `h` grid rows, giving `{stem}_next_{h}h` = total `col` expected to fall in
    the OPEN-CLOSED window `(s, s+h]` measured from row `s`'s timestamp (`stem`
    drops the `_mm` suffix, e.g. `precip_mm` -> `precip_next_24h`). Rows whose
    forward window runs past the end of the frame get NaN (never a partial,
    silently-short sum).

    Why `(s, s+h]` specifically: `run_experiment` builds decision-time features
    as `X = numeric.shift(h)`, so the value the model sees for target row `t`
    is this column read at row `t - h`, i.e. the sum over `(t-h, t]` — exactly
    the window a weather forecast issued at decision time `t-h` would have to
    cover to be useful for a `t`-ahead prediction. That's a real, physically
    grounded feature, not future information *about the target itself*.

    What it is NOT: a free source of truth for the target's own future value.
    In this backtest the sums come from *actual* recorded weather, i.e. a
    perfect-forecast proxy — the honest upper bound on what a real forecast
    (see `vine.d1_pipeline.weather.fetch_forecast`, which would fill this same
    column live) could contribute; a live-serving system would only ever see
    a forecast's uncertainty, not the truth. This is a deliberate, labeled
    stand-in, not a leak, PROVIDED the horizon guard is respected: a
    `_next_48h` column read at decision time for a `6h`-ahead target covers
    `(t-6, t+42]` — 42 hours *past* the target time `t`. That genuinely leaks
    the target's own future and must never be fed to a model at a mismatched
    horizon; `run_experiment` enforces this by dropping every `_next_*` column
    whose horizon suffix doesn't equal the horizon being scored.

    Args:
        frame: feature frame with `attach_weather` already applied (so `cols`
            carry the forward-filled daily totals).
        horizons_h: horizons (in grid rows) to build lead-time sums for.
        cols: forward-filled daily weather columns to convert.
    """
    out = frame.copy()
    for col in cols:
        if col not in out.columns:
            continue
        rate = out[col] / 24.0  # daily total -> implied hourly rate
        stem = col.removesuffix("_mm")
        for h in horizons_h:
            # Forward sum of the next h hourly rates (excluding the current
            # row): shift the rate back by one row, then take a *backward*
            # rolling sum on the time-reversed series and reverse it back —
            # the standard trick for a forward-looking window with min_periods
            # enforcing NaN wherever the window would run off the end.
            shifted = rate.shift(-1)
            fwd_sum = shifted[::-1].rolling(window=h, min_periods=h).sum()[::-1]
            out[f"{stem}_next_{h}h"] = fwd_sum
    return out

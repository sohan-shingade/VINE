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

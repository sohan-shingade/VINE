"""Offline data-profile helpers for the D1 executable datasheet.

The functions in this module summarize already-pinned snapshots. They never
fetch live services and never impute missing sensor values.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from vine.d1_pipeline.geo import assign_sensors_to_blocks
from vine.d1_pipeline.sensors import resample
from vine.d1_pipeline.validation import gap_report


def _longest_gap(mask: pd.Series) -> int:
    """Longest consecutive True run in a boolean series."""
    groups = mask.ne(mask.shift()).cumsum()
    lengths = mask.groupby(groups).sum()
    return int(lengths.max()) if len(lengths) else 0


def sensor_coverage(
    frames: Mapping[str, pd.DataFrame],
    *,
    freq: str = "1h",
) -> pd.DataFrame:
    """Profile rows, cadence, and regular-grid missingness per numeric channel."""
    rows: list[dict[str, Any]] = []
    for device in sorted(frames):
        frame = frames[device].sort_index()
        if not isinstance(frame.index, pd.DatetimeIndex) or frame.empty:
            continue
        numeric = frame.select_dtypes("number")
        regular = resample(numeric, freq)
        gaps = gap_report(numeric, freq)
        deltas = frame.index.to_series().diff().dropna().dt.total_seconds() / 60.0
        for channel in numeric.columns:
            missing = int(gaps[channel])
            expected = len(regular)
            rows.append(
                {
                    "device": device,
                    "channel": channel,
                    "raw_rows": int(numeric[channel].notna().sum()),
                    "start": frame.index.min(),
                    "end": frame.index.max(),
                    "median_cadence_min": float(deltas.median()) if len(deltas) else float("nan"),
                    "p90_cadence_min": float(deltas.quantile(0.9)) if len(deltas) else float("nan"),
                    "expected_bins": expected,
                    "observed_bins": expected - missing,
                    "missing_bins": missing,
                    "missing_pct": 100.0 * missing / expected if expected else 0.0,
                    "longest_gap_bins": _longest_gap(regular[channel].isna()),
                }
            )
    return pd.DataFrame(rows)


def weekly_missingness(
    frames: Mapping[str, pd.DataFrame],
    *,
    channels: Mapping[str, str] | None = None,
    freq: str = "1h",
    week: str = "W-MON",
) -> pd.DataFrame:
    """Return tidy weekly missing fractions for one channel per device."""
    rows: list[pd.DataFrame] = []
    for device in sorted(frames):
        frame = frames[device].sort_index()
        if frame.empty:
            continue
        channel = (
            channels[device] if channels else next(iter(frame.select_dtypes("number").columns))
        )
        regular = resample(frame[[channel]], freq)[channel]
        weekly = regular.isna().resample(week).mean()
        rows.append(
            pd.DataFrame(
                {
                    "week": weekly.index,
                    "device": device,
                    "channel": channel,
                    "missing_fraction": weekly.to_numpy(),
                }
            )
        )
    if not rows:
        return pd.DataFrame(columns=["week", "device", "channel", "missing_fraction"])
    return pd.concat(rows, ignore_index=True)


def weather_coverage(
    sensor_index: pd.DatetimeIndex,
    weather: pd.DataFrame,
    *,
    columns: Sequence[str] = ("precip_mm", "et0_mm"),
) -> pd.DataFrame:
    """Report daily weather availability across a sensor timeline."""
    if sensor_index.empty:
        return pd.DataFrame(columns=["channel", "expected_days", "covered_days", "coverage_pct"])
    sensor_days = pd.DatetimeIndex(sensor_index).tz_localize(None)
    days = pd.date_range(sensor_days.min().normalize(), sensor_days.max().normalize(), freq="1D")
    weather_daily = weather.copy()
    weather_index = pd.DatetimeIndex(weather_daily.index)
    if weather_index.tz is not None:
        weather_index = weather_index.tz_localize(None)
    weather_daily.index = weather_index.normalize()
    rows = []
    for column in columns:
        values = (
            weather_daily[column].reindex(days)
            if column in weather_daily
            else pd.Series(index=days)
        )
        covered = int(values.notna().sum())
        rows.append(
            {
                "channel": column,
                "expected_days": len(days),
                "covered_days": covered,
                "coverage_pct": 100.0 * covered / len(days),
            }
        )
    return pd.DataFrame(rows)


def select_deployed_points(points: Any, device_ids: Sequence[str]) -> Any:
    """Keep KMZ points whose names exactly match pinned sensor device IDs."""
    return points[points["name"].isin(device_ids)].copy()


def block_alignment_summary(blocks: Any, points: Any, device_ids: Sequence[str]) -> pd.DataFrame:
    """Spatially align deployed points and retain unmatched devices explicitly."""
    deployed = select_deployed_points(points, device_ids)
    aligned = assign_sensors_to_blocks(deployed, blocks)
    return pd.DataFrame({"device": list(device_ids)}).merge(
        aligned.rename(columns={"name": "device"}), on="device", how="left"
    )


def dvc_snapshot_manifest(paths: Sequence[str | Path]) -> pd.DataFrame:
    """Read hashes, sizes, and output paths from DVC pointer files."""
    rows = []
    for path_like in paths:
        path = Path(path_like)
        payload = yaml.safe_load(path.read_text())
        for out in payload.get("outs", []):
            rows.append(
                {
                    "pointer": str(path),
                    "path": out.get("path"),
                    "md5": out.get("md5"),
                    "size_bytes": out.get("size"),
                    "nfiles": out.get("nfiles", 1),
                }
            )
    return pd.DataFrame(rows)


def read_imagery_inventory(path: str | Path) -> pd.DataFrame:
    """Load and validate the small offline imagery manifest."""
    inventory = pd.read_parquet(path)
    required = {"acquisition", "block_id", "asset_kind", "band", "available"}
    missing = required - set(inventory.columns)
    if missing:
        raise ValueError(f"imagery inventory missing columns: {sorted(missing)}")
    return inventory.sort_values(["acquisition", "block_id", "asset_kind", "band"]).reset_index(
        drop=True
    )

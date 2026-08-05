"""Run the label-free D4 GDD phenology exploration.

Climate context only — no harvest prediction, no labels (see
`vine.d4_harvest.phenology`). Reads a local daily-weather snapshot if the
config names one, else pulls the Open-Meteo archive for the configured seasons.

    uv run python scripts/d4_gdd.py configs/d4_harvest/gdd_exploration.yaml
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from vine.common.config import load_config
from vine.d1_pipeline.weather import fetch_historical
from vine.d4_harvest.phenology import GddExplorationConfig, explore_seasons


def load_weather(cfg: GddExplorationConfig) -> pd.DataFrame:
    """Read the configured snapshot if present, else fetch the archive live."""
    if cfg.snapshot_csv:
        path = Path(cfg.snapshot_csv)
        if path.exists():
            frame = pd.read_csv(path, parse_dates=["date"]).set_index("date")
            print(f"read {len(frame)} daily rows from {path}")
            return frame
        print(f"(snapshot {path} not found — fetching Open-Meteo archive)")
    start = min(season.start for season in cfg.seasons)
    # The archive rejects future dates; an in-season window simply stops today.
    end = min(max(season.end for season in cfg.seasons), pd.Timestamp.today().strftime("%Y-%m-%d"))
    frame = fetch_historical(start, end, lat=cfg.lat, lon=cfg.lon)
    print(f"fetched {len(frame)} daily rows from Open-Meteo archive [{start} .. {end}]")
    return frame


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", help="YAML GDD-exploration config")
    args = parser.parse_args()

    cfg = GddExplorationConfig(**load_config(Path(args.config)))
    weather = load_weather(cfg)
    trajectories, crossings = explore_seasons(weather, cfg)

    for path, frame in ((cfg.output_path, trajectories), (cfg.crossings_path, crossings)):
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(out, index=False)

    summary = crossings.drop_duplicates("season")[
        ["season", "season_days", "season_missing_days", "season_gdd_total", "winkler_region"]
    ]
    print(f"\nseason totals (GDD base {cfg.base_temp_c:.1f} C):")
    print(summary.to_string(index=False, float_format=lambda v: f"{v:.1f}"))
    print("\nband crossings:")
    print(
        crossings[
            [
                "season",
                "band",
                "edge",
                "gdd_threshold",
                "crossed_date",
                "day_of_season",
                "complete",
            ]
        ].to_string(index=False, float_format=lambda v: f"{v:.0f}")
    )
    print(f"\nwrote {len(trajectories)} trajectory rows to {cfg.output_path}")
    print(f"wrote {len(crossings)} crossing rows to {cfg.crossings_path}")
    print("\nThis is climate context, NOT a harvest recommendation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

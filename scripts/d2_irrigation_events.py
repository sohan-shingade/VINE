"""Catalog inferred irrigation events from the pinned soil-probe snapshots (D2).

Loads the five IHV soil probes (SE01-LS-1..4 plus SE0X-LS-1) and the daily
weather snapshot, regularizes each probe to the hourly grid, detects sharp
sustained soil-moisture rises, attributes rises coinciding with recorded rain
to rain, and writes the rest as inferred irrigation events. Offline only: no
network, no MLflow.

    uv run python scripts/d2_irrigation_events.py

Detection parameters used here (defaults of `vine.d2_irrigation.events`):
min_jump=0.5 sensor units, max_span_h=12 hours, rise_tol=0.0, rain
attribution at >= 1.0 mm daily precipitation on the event day or the day
before. With min_jump=1.0 every detected event is rain; the candidate
irrigation rises on zero-rain days sit between 0.5 and 1.0 units, hence 0.5.

Writes docs/reports/assets/d2_inferred_irrigation_events.csv (sorted by
device then start, deterministic) and prints a per-probe summary.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from vine.d1_pipeline import sensors
from vine.d1_pipeline.ingest import load_snapshot, load_weather_snapshot
from vine.d2_irrigation.data import SOIL_DEVICES, normalize_soil_probe
from vine.d2_irrigation.events import attribute_rain, detect_rise_events

OUT_CSV = Path("docs/reports/assets/d2_inferred_irrigation_events.csv")


def main() -> int:
    weather = load_weather_snapshot()
    if weather is None:
        print("no weather snapshot found; aborting")
        return 1
    precip = weather["precip_mm"]

    catalogs: list[pd.DataFrame] = []
    for device in SOIL_DEVICES:
        raw = normalize_soil_probe(load_snapshot(device), device)
        soil = pd.to_numeric(raw["soil_water"], errors="coerce")
        grid = sensors.resample(soil.to_frame("soil_water"), "1h")["soil_water"]
        events = attribute_rain(detect_rise_events(grid), precip)
        events.insert(0, "device", device)
        catalogs.append(events)
        irrigation = (events["attribution"] == "irrigation").sum()
        rain = (events["attribution"] == "rain").sum()
        print(
            f"{device}: {len(grid):,} hourly rows, {len(events)} rise events "
            f"({irrigation} irrigation, {rain} rain)"
        )

    catalog = pd.concat(catalogs, ignore_index=True)
    catalog = catalog.sort_values(["device", "start"]).reset_index(drop=True)
    for col in ("trough", "peak", "jump"):
        catalog[col] = catalog[col].round(3)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    catalog.to_csv(OUT_CSV, index=False)

    irrigation = catalog[catalog["attribution"] == "irrigation"]
    print(f"\nwrote {OUT_CSV} ({len(catalog)} events, {len(irrigation)} inferred irrigation)")
    if not irrigation.empty:
        print("\ninferred irrigation events:")
        print(irrigation.to_string(index=False))
        print(f"\nmedian irrigation jump: {irrigation['jump'].median():.3f} sensor units")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

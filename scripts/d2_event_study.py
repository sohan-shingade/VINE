"""Event-conditioned evaluation (event study) of D2 forecasts across probes.

Aggregate MAE over roughly 1,350 mostly quiet holdout hours dilutes the rare
hours where persistence is worst: rain fronts and irrigation jumps, each
followed by a drainage transient. This runner detects rise events per probe
with the settled parameters of scripts/d2_irrigation_events.py, marks every
scored target hour inside an event window plus a trailing 24 h as the event
subset, and scores persistence, diurnal drift, and the vintage-forecast
water-balance challenger separately on event hours and on quiet hours. It
also reports the event subset's share of persistence's total absolute error,
which quantifies the dilution claim.

    uv run python scripts/d2_event_study.py configs/d2_irrigation/event_study.yaml

Writes docs/reports/assets/d2_event_study_results.csv and logs to MLflow
(experiment d2_irrigation, run name event-study).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from vine.common.config import REPO_ROOT, load_config, settings
from vine.common.seed import seed_everything
from vine.d1_pipeline import sensors
from vine.d1_pipeline.ingest import load_snapshot, load_weather_snapshot
from vine.d2_irrigation.config import IrrigationConfig
from vine.d2_irrigation.data import load_soil_probe_frames, normalize_soil_probe
from vine.d2_irrigation.event_study import run_event_study
from vine.d2_irrigation.events import attribute_rain, detect_rise_events

OUT_CSV = REPO_ROOT / "docs" / "reports" / "assets" / "d2_event_study_results.csv"


def load_vintage_snapshot(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Load the archived-forecast snapshot covering all probe frames, else fetch it.

    Same snapshot path convention as scripts/d2_water_balance.py, so the
    vintage evaluation reuses the exact parquet the earlier experiment pinned.
    """
    from vine.d1_pipeline.weather import fetch_forecast_vintages

    start = min(f.index.min() for f in frames.values()).strftime("%Y-%m-%d")
    end = max(f.index.max() for f in frames.values()).strftime("%Y-%m-%d")
    path = settings.data_dir / "raw" / "weather" / f"forecast_vintages_{start}_{end}.parquet"
    if path.exists():
        vintages = pd.read_parquet(path)
        print(f"loaded vintage snapshot {path} ({len(vintages)} hourly rows)")
    else:
        vintages = fetch_forecast_vintages(start, end)
        path.parent.mkdir(parents=True, exist_ok=True)
        vintages.to_parquet(path)
        print(f"fetched + snapshotted vintages to {path} ({len(vintages)} hourly rows)")
    return vintages


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "config",
        nargs="?",
        default="configs/d2_irrigation/event_study.yaml",
        help="YAML experiment config",
    )
    parser.add_argument("--no-mlflow", action="store_true")
    args = parser.parse_args()

    raw_cfg = load_config(Path(args.config))
    detection = raw_cfg.pop("event_detection", {})
    trailing_h = int(detection.pop("trailing_h", 24))
    rain_mm = float(detection.pop("rain_mm", 1.0))
    cfg = IrrigationConfig(**raw_cfg)
    seed = seed_everything()

    weather = load_weather_snapshot()
    if weather is None:
        print("no weather snapshot found; aborting")
        return 1
    precip = weather["precip_mm"]

    frames = load_soil_probe_frames()
    vintages = load_vintage_snapshot(frames) if cfg.weather_source == "vintage" else None

    tables = []
    share_rows = []
    for device, frame in frames.items():
        probe = normalize_soil_probe(load_snapshot(device), device)
        soil = pd.to_numeric(probe["soil_water"], errors="coerce")
        grid = sensors.resample(soil.to_frame("soil_water"), "1h")["soil_water"]
        events = attribute_rain(detect_rise_events(grid, **detection), precip, rain_mm=rain_mm)
        device_cfg = cfg.model_copy(update={"device": device})
        result, shares = run_event_study(
            frame, device_cfg, events, vintages=vintages, trailing_h=trailing_h
        )
        result.insert(0, "device", device)
        tables.append(result)
        share_rows.extend(
            {"device": device, "horizon_h": h, "event_error_share": s} for h, s in shares.items()
        )
        rain = int((events["attribution"] == "rain").sum())
        irrigation = int((events["attribution"] == "irrigation").sum())
        print(f"evaluated {device}: {len(events)} events ({rain} rain, {irrigation} irrigation)")

    results = pd.concat(tables, ignore_index=True)
    shares_table = pd.DataFrame(share_rows)
    print(results.to_string(index=False, float_format=lambda value: f"{value:.3f}"))
    print("\nevent-subset share of persistence's total absolute error:")
    print(shares_table.to_string(index=False, float_format=lambda value: f"{value:.3f}"))

    results.round(4).to_csv(OUT_CSV, index=False)
    print(f"wrote {OUT_CSV}")

    if not args.no_mlflow:
        try:
            import mlflow
        except ImportError:
            print("\n(mlflow not installed, skipped logging)")
            return 0
        mlflow.set_experiment("d2_irrigation")
        with mlflow.start_run(run_name="event-study") as run:
            mlflow.log_params(
                {
                    **cfg.model_dump(),
                    **detection,
                    "rain_mm": rain_mm,
                    "trailing_h": trailing_h,
                    "seed": seed,
                    "sensors": list(frames),
                }
            )
            mlflow.log_text(results.to_csv(index=False), "event_study_results.csv")
            mlflow.log_text(shares_table.to_csv(index=False), "event_error_shares.csv")
            for row in shares_table.itertuples():
                mlflow.log_metric(
                    f"event_error_share_{row.device}_{row.horizon_h}h", row.event_error_share
                )
            challengers = results[results.model != "persistence"]
            for row in challengers[challengers.subset == "event"].itertuples():
                tag = f"{row.model}_{row.device}_{row.horizon_h}h"
                mlflow.log_metric(f"skill_event_{tag}", row.skill_vs_persistence)
                mlflow.log_metric(f"n_event_{row.device}_{row.horizon_h}h", row.n)
            for row in challengers[challengers.subset == "quiet"].itertuples():
                tag = f"{row.model}_{row.device}_{row.horizon_h}h"
                mlflow.log_metric(f"skill_quiet_{tag}", row.skill_vs_persistence)
            print(f"mlflow run id: {run.info.run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

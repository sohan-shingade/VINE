"""Evaluate the D2 rain-gated persistence hybrid across every soil probe.

The event study showed the water-balance correction wins rain-event windows
at 24 and 48 h under real archived forecast vintages and loses quiet hours
where it fires with nothing happening. This runner evaluates the obvious
hybrid: persistence by default, the water-balance forecast only when the
forecast at the origin predicts material rain over the horizon window. One
global gate threshold is selected per walk-forward fold on the training
window alone; every candidate threshold is also reported so the sensitivity
is visible.

    uv run python scripts/d2_gated.py configs/d2_irrigation/gated.yaml

Writes docs/reports/assets/d2_gated_results.csv and logs to MLflow
(experiment d2_irrigation, run name gated-water-balance).
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pandas as pd

from vine.common.config import REPO_ROOT, load_config, settings
from vine.common.seed import seed_everything
from vine.d1_pipeline import sensors
from vine.d1_pipeline.ingest import load_snapshot, load_weather_snapshot
from vine.d2_irrigation.config import IrrigationConfig
from vine.d2_irrigation.data import load_soil_probe_frames, normalize_soil_probe
from vine.d2_irrigation.events import attribute_rain, detect_rise_events
from vine.d2_irrigation.gated import THRESHOLDS_MM, run_gated

OUT_CSV = REPO_ROOT / "docs" / "reports" / "assets" / "d2_gated_results.csv"


def load_vintage_snapshot(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Load the archived-forecast snapshot covering all probe frames, else fetch it.

    Same snapshot path convention as scripts/d2_water_balance.py, so this
    evaluation reuses the exact parquet the earlier experiments pinned.
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
        default="configs/d2_irrigation/gated.yaml",
        help="YAML experiment config",
    )
    parser.add_argument("--no-mlflow", action="store_true")
    args = parser.parse_args()

    raw_cfg = load_config(Path(args.config))
    detection = raw_cfg.pop("event_detection", {})
    trailing_h = int(detection.pop("trailing_h", 24))
    rain_mm = float(detection.pop("rain_mm", 1.0))
    gate = raw_cfg.pop("gate", {})
    thresholds_mm = tuple(float(t) for t in gate.get("thresholds_mm", THRESHOLDS_MM))
    val_frac = float(gate.get("val_frac", 0.25))
    cfg = IrrigationConfig(**raw_cfg)
    if cfg.weather_source != "vintage":
        raise ValueError("the gated hybrid is defined on archived vintages; set weather_source")
    seed = seed_everything()

    weather = load_weather_snapshot()
    if weather is None:
        print("no weather snapshot found; aborting")
        return 1
    precip = weather["precip_mm"]

    frames = load_soil_probe_frames()
    vintages = load_vintage_snapshot(frames)

    tables = []
    selected_rows = []
    for device, frame in frames.items():
        probe = normalize_soil_probe(load_snapshot(device), device)
        soil = pd.to_numeric(probe["soil_water"], errors="coerce")
        grid = sensors.resample(soil.to_frame("soil_water"), "1h")["soil_water"]
        events = attribute_rain(detect_rise_events(grid, **detection), precip, rain_mm=rain_mm)
        device_cfg = cfg.model_copy(update={"device": device})
        result, selected = run_gated(
            frame,
            device_cfg,
            events,
            vintages=vintages,
            thresholds_mm=thresholds_mm,
            trailing_h=trailing_h,
            val_frac=val_frac,
        )
        result.insert(0, "device", device)
        tables.append(result)
        selected_rows.extend(
            {"device": device, "horizon_h": h, "selected_per_fold": per_fold}
            for h, per_fold in selected.items()
        )
        print(f"evaluated {device}: {len(events)} events, selected thresholds {selected}")

    results = pd.concat(tables, ignore_index=True)
    selected_table = pd.DataFrame(selected_rows)
    print(results.to_string(index=False, float_format=lambda value: f"{value:.3f}"))
    print("\nselected threshold per fold:")
    print(selected_table.to_string(index=False))

    results.round(4).to_csv(OUT_CSV, index=False)
    print(f"wrote {OUT_CSV}")

    if not args.no_mlflow:
        try:
            import mlflow
        except ImportError:
            print("\n(mlflow not installed, skipped logging)")
            return 0
        uri = os.environ.get("MLFLOW_TRACKING_URI") or f"sqlite:///{REPO_ROOT / 'mlflow.db'}"
        mlflow.set_tracking_uri(uri)
        mlflow.set_experiment("d2_irrigation")
        with mlflow.start_run(run_name="gated-water-balance") as run:
            mlflow.log_params(
                {
                    **cfg.model_dump(),
                    **detection,
                    "rain_mm": rain_mm,
                    "trailing_h": trailing_h,
                    "gate_thresholds_mm": list(thresholds_mm),
                    "gate_val_frac": val_frac,
                    "seed": seed,
                    "sensors": list(frames),
                }
            )
            mlflow.log_text(results.to_csv(index=False), "gated_results.csv")
            mlflow.log_text(selected_table.to_csv(index=False), "selected_thresholds.csv")
            sel = results[results.model == "gated_wb_selected"]
            for row in sel.itertuples():
                tag = f"{row.device}_{row.horizon_h}h_{row.subset}"
                if pd.notna(row.skill_vs_persistence):
                    mlflow.log_metric(f"skill_{tag}", row.skill_vs_persistence)
                if pd.notna(row.skill_fold_min):
                    mlflow.log_metric(f"skill_fold_min_{tag}", row.skill_fold_min)
                if row.subset == "all":
                    mlflow.log_metric(
                        f"gate_fired_frac_{row.device}_{row.horizon_h}h", row.gate_fired_frac
                    )
            print(f"mlflow run id: {run.info.run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

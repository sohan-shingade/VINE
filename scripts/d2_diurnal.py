"""Evaluate the diurnal-drift baselines across every soil probe (D2).

Runs the shared purged walk-forward harness on all five IHV probes and writes
the tidy results table to docs/reports/assets/d5_diurnal_results.csv. The two
new rows per probe and horizon are diurnal_drift (persistence plus expected
cumulative hour-of-day drift fit in delta space) and diurnal_drift_temp (the
same table conditioned on the decision-time soil temperature tercile).

    uv run python scripts/d2_diurnal.py configs/d2_irrigation/diurnal.yaml
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from vine.common.config import REPO_ROOT, load_config
from vine.common.seed import seed_everything
from vine.d2_irrigation.config import IrrigationConfig
from vine.d2_irrigation.data import load_soil_probe_frames
from vine.d2_irrigation.experiment import run_experiment

DIURNAL_MODELS = ("diurnal_drift", "diurnal_drift_temp")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "config",
        nargs="?",
        default="configs/d2_irrigation/diurnal.yaml",
        help="YAML experiment config",
    )
    parser.add_argument("--no-mlflow", action="store_true")
    args = parser.parse_args()

    cfg = IrrigationConfig(**load_config(Path(args.config)))
    seed = seed_everything()
    frames = load_soil_probe_frames()

    tables = []
    for device, frame in frames.items():
        device_cfg = cfg.model_copy(update={"device": device})
        result = run_experiment(frame, device_cfg)
        result.insert(0, "device", device)
        tables.append(result)
        print(f"evaluated {device}", flush=True)
    results = pd.concat(tables, ignore_index=True)
    print(results.to_string(index=False, float_format=lambda value: f"{value:.3f}"))

    out = REPO_ROOT / "docs" / "reports" / "assets" / "d5_diurnal_results.csv"
    results.round(3).to_csv(out, index=False)
    print(f"wrote {out}")

    if not args.no_mlflow:
        try:
            import mlflow
        except ImportError:
            print("\n(mlflow not installed, skipped logging)")
            return 0
        mlflow.set_experiment("d2_irrigation")
        with mlflow.start_run(run_name="diurnal-drift-all-sensors") as run:
            mlflow.log_params({**cfg.model_dump(), "seed": seed, "sensors": list(frames)})
            mlflow.log_text(results.to_csv(index=False), "diurnal_results.csv")
            for row in results[results.model.isin(DIURNAL_MODELS)].itertuples():
                tag = f"{row.model}_{row.device}_{row.horizon_h}h"
                mlflow.log_metric(f"mae_{tag}", row.mae)
                mlflow.log_metric(f"skill_{tag}", row.skill_vs_persistence)
                mlflow.log_metric(f"skill_fold_median_{tag}", row.skill_fold_median)
                mlflow.log_metric(f"skill_fold_min_{tag}", row.skill_fold_min)
            print(f"mlflow run id: {run.info.run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Evaluate the D2 water-balance upper bound across every soil probe.

Historical backtests use the labeled perfect-forecast weather proxy. Results are
therefore an upper bound, not a claim about live forecast skill.

    uv run python scripts/d2_water_balance.py configs/d2_irrigation/water_balance.yaml
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from vine.common.config import load_config
from vine.common.seed import seed_everything
from vine.d2_irrigation.config import IrrigationConfig
from vine.d2_irrigation.data import load_soil_probe_frames
from vine.d2_irrigation.experiment import run_experiment


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", help="YAML water-balance config")
    parser.add_argument("--no-mlflow", action="store_true")
    args = parser.parse_args()

    cfg = IrrigationConfig(**load_config(Path(args.config)))
    if cfg.model != "water_balance":
        raise ValueError("config model must be water_balance")
    seed = seed_everything()
    frames = load_soil_probe_frames()

    tables = []
    for device, frame in frames.items():
        device_cfg = cfg.model_copy(update={"device": device})
        result = run_experiment(frame, device_cfg)
        result.insert(0, "device", device)
        tables.append(result)
    results = pd.concat(tables, ignore_index=True)
    print(results.to_string(index=False, float_format=lambda value: f"{value:.3f}"))

    if not args.no_mlflow:
        try:
            import mlflow
        except ImportError:
            print("\n(mlflow not installed — skipped logging)")
            return 0
        mlflow.set_experiment("d2_irrigation")
        with mlflow.start_run(run_name="water-balance-all-sensors"):
            mlflow.log_params({**cfg.model_dump(), "seed": seed, "sensors": list(frames)})
            mlflow.log_text(results.to_csv(index=False), "water_balance_results.csv")
            wb = results[results.model == "water_balance"]
            for row in wb.itertuples():
                tag = f"{row.device}_{row.horizon_h}h"
                mlflow.log_metric(f"mae_{tag}", row.mae)
                mlflow.log_metric(f"rmse_{tag}", row.rmse)
                mlflow.log_metric(f"skill_{tag}", row.skill_vs_persistence)
                mlflow.log_metric(f"skill_fold_median_{tag}", row.skill_fold_median)
                mlflow.log_metric(f"skill_fold_min_{tag}", row.skill_fold_min)
                mlflow.log_metric(f"precision_{tag}", row.precision)
                mlflow.log_metric(f"recall_{tag}", row.recall)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

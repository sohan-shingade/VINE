"""Evaluate the probabilistic (CRPS) challenger across probes (D2).

Runs the shared purged walk-forward harness on all five IHV soil probes and
writes the tidy results table to docs/reports/assets/d2_crps_results.csv.
Every model keeps persistence as the forecast center; what varies is the
predictive spread (see `vine.d2_irrigation.probabilistic`). The persistence
point mass is the reference, and its CRPS equals its MAE, so any positive
CRPS skill measures the value of the spread alone.

    uv run python scripts/d2_probabilistic.py configs/d2_irrigation/probabilistic.yaml
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from vine.common.config import REPO_ROOT, load_config
from vine.common.seed import seed_everything
from vine.d2_irrigation.config import IrrigationConfig
from vine.d2_irrigation.data import load_soil_probe_frames
from vine.d2_irrigation.probabilistic import run_probabilistic_experiment


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "config",
        nargs="?",
        default="configs/d2_irrigation/probabilistic.yaml",
        help="YAML experiment config",
    )
    parser.add_argument("--no-mlflow", action="store_true")
    args = parser.parse_args()

    cfg = IrrigationConfig(**load_config(Path(args.config)))
    seed = seed_everything()
    frames = load_soil_probe_frames()
    for device, frame in frames.items():
        observed = frame[cfg.target].notna().sum()
        print(f"  {device}: {len(frame):,} hourly rows, {observed:,} observed")

    results = run_probabilistic_experiment(frames, cfg)
    print(results.to_string(index=False, float_format=lambda value: f"{value:.3f}"))

    out = REPO_ROOT / "docs" / "reports" / "assets" / "d2_crps_results.csv"
    results.round(4).to_csv(out, index=False)
    print(f"wrote {out}")

    if not args.no_mlflow:
        try:
            import mlflow
        except ImportError:
            print("\n(mlflow not installed, skipped logging)")
            return 0
        uri = os.environ.get("MLFLOW_TRACKING_URI") or f"sqlite:///{REPO_ROOT / 'mlflow.db'}"
        mlflow.set_tracking_uri(uri)
        mlflow.set_experiment("d2_irrigation")
        with mlflow.start_run(run_name="crps-probabilistic") as run:
            mlflow.log_params({**cfg.model_dump(), "seed": seed, "sensors": list(frames)})
            mlflow.log_text(results.to_csv(index=False), "crps_results.csv")
            for row in results[results.model != "persistence-point"].itertuples():
                tag = f"{row.model.replace('-', '_')}_{row.device}_{row.horizon_h}h"
                mlflow.log_metric(f"crps_{tag}", row.crps)
                mlflow.log_metric(f"crps_skill_{tag}", row.crps_skill)
                mlflow.log_metric(f"crps_skill_fold_min_{tag}", row.crps_skill_fold_min)
                mlflow.log_metric(f"cov90_{tag}", row.cov90)
            print(f"mlflow run id: {run.info.run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

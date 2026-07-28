"""Run label-free D3 vegetation-index stress screening."""

from __future__ import annotations

import argparse
from pathlib import Path

from vine.common.config import load_config
from vine.common.seed import seed_everything
from vine.d3_vision.stress import StressRankingConfig, screen_rasters


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", help="YAML stress-screening config")
    parser.add_argument("--no-mlflow", action="store_true")
    args = parser.parse_args()

    cfg = StressRankingConfig(**load_config(Path(args.config)))
    seed_everything(cfg.seed)
    results = screen_rasters(cfg)
    cfg.output_path.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(cfg.output_path, index=False)
    print(results.to_string(index=False, float_format=lambda value: f"{value:.3f}"))
    print(f"\nwrote {len(results)} block rows to {cfg.output_path}")

    if not args.no_mlflow:
        try:
            import mlflow
        except ImportError:
            print("(mlflow not installed — skipped logging)")
            return 0
        mlflow.set_experiment(cfg.mlflow_experiment)
        with mlflow.start_run(run_name=f"stress-screening-{cfg.acquisition}"):
            mlflow.log_params(cfg.model_dump(mode="json"))
            mlflow.log_metric("blocks", len(results))
            mlflow.log_metric("quality_blocks", int(results.quality_ok.sum()))
            mlflow.log_artifact(cfg.output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

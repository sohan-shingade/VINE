"""Evaluate the error-correction (cointegration) challenger across probes (D2).

Runs the shared purged walk-forward harness on all five IHV soil probes and
writes the tidy results table to docs/reports/assets/d5_ecm_results.csv. Each
probe's forecast is its last observed level plus an error-correction term on
its spread against the other probes' standardized levels (see
`vine.d2_irrigation.ecm`). Diagnostics report the fitted coefficients and the
training spread's AR(1) slope per fold, so the mean-reversion premise is
checkable either way the skill numbers land.

    uv run python scripts/d2_ecm.py configs/d2_irrigation/ecm.yaml
"""

from __future__ import annotations

import argparse
from pathlib import Path

from vine.common.config import REPO_ROOT, load_config
from vine.common.seed import seed_everything
from vine.d2_irrigation.config import IrrigationConfig
from vine.d2_irrigation.data import load_soil_probe_frames
from vine.d2_irrigation.ecm import run_ecm_experiment


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "config",
        nargs="?",
        default="configs/d2_irrigation/ecm.yaml",
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

    results, diagnostics = run_ecm_experiment(frames, cfg)
    print(results.to_string(index=False, float_format=lambda value: f"{value:.3f}"))
    print("\nper-fold diagnostics (coefficients + spread AR(1) slope):")
    print(diagnostics.to_string(index=False, float_format=lambda value: f"{value:.3f}"))

    out = REPO_ROOT / "docs" / "reports" / "assets" / "d5_ecm_results.csv"
    results.round(3).to_csv(out, index=False)
    print(f"wrote {out}")

    if not args.no_mlflow:
        try:
            import mlflow
        except ImportError:
            print("\n(mlflow not installed, skipped logging)")
            return 0
        mlflow.set_experiment("d2_irrigation")
        with mlflow.start_run(run_name="ecm-all-sensors") as run:
            mlflow.log_params({**cfg.model_dump(), "seed": seed, "sensors": list(frames)})
            mlflow.log_text(results.to_csv(index=False), "ecm_results.csv")
            mlflow.log_text(diagnostics.to_csv(index=False), "ecm_diagnostics.csv")
            for row in results[results.model == "ecm"].itertuples():
                tag = f"ecm_{row.device}_{row.horizon_h}h"
                mlflow.log_metric(f"mae_{tag}", row.mae)
                mlflow.log_metric(f"skill_{tag}", row.skill_vs_persistence)
                mlflow.log_metric(f"skill_fold_median_{tag}", row.skill_fold_median)
                mlflow.log_metric(f"skill_fold_min_{tag}", row.skill_fold_min)
            print(f"mlflow run id: {run.info.run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

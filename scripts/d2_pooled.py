"""Run the pooled cross-sensor D2 experiment on the real snapshots.

Loads all five IHV soil probes (SE01-LS-1..4 + the recovered SE0X-LS-1),
builds D1 features + weather for each, and evaluates one globally-pooled model
against each sensor's own persistence baseline (see `vine.d2_irrigation.pooled`).

    uv run python scripts/d2_pooled.py configs/d2_irrigation/pooled_gbt.yaml
    uv run python scripts/d2_pooled.py configs/d2_irrigation/pooled_ridge.yaml --no-mlflow

This is the cross-learning rung the per-sensor ladder could not test. Reproducible
by construction: YAML config + `seed_everything()`.
"""

from __future__ import annotations

import argparse

from vine.common.seed import seed_everything
from vine.d2_irrigation.config import IrrigationConfig
from vine.d2_irrigation.data import SOIL_DEVICES, load_soil_probe_frames
from vine.d2_irrigation.pooled import run_pooled_experiment


def main() -> int:
    from pathlib import Path

    from vine.common.config import load_config

    ap = argparse.ArgumentParser()
    ap.add_argument(
        "config",
        nargs="?",
        default="configs/d2_irrigation/pooled_gbt.yaml",
        help="YAML experiment config",
    )
    ap.add_argument("--no-mlflow", action="store_true")
    args = ap.parse_args()

    cfg = IrrigationConfig(**load_config(Path(args.config)))
    seed = seed_everything()

    print(f"loading {len(SOIL_DEVICES)} soil sensors...")
    frames = load_soil_probe_frames()
    for device, frame in frames.items():
        observed = frame["soil_water"].notna().sum()
        print(f"  {device}: {len(frame):,} hourly rows, {observed:,} observed")
    if len(frames) < 2:
        print("need >=2 sensors to pool; aborting")
        return 1

    print(f"\npooled walk-forward: model={cfg.model}, {len(frames)} sensors, seed={seed}\n")
    results = run_pooled_experiment(frames, cfg)
    print(results.to_string(index=False, float_format=lambda v: f"{v:.3f}"))

    if not args.no_mlflow:
        try:
            import mlflow

            mlflow.set_experiment("d2_irrigation")
            with mlflow.start_run(run_name=f"pooled-{cfg.model}"):
                mlflow.log_params({**cfg.model_dump(), "seed": seed, "sensors": list(frames)})
                for r in results.itertuples():
                    tag = f"{r.device}_{r.model}_{r.horizon_h}h"
                    mlflow.log_metric(f"mae_{tag}", r.mae)
                    mlflow.log_metric(f"skill_{tag}", r.skill_vs_persistence)
        except ImportError:
            print("\n(mlflow not installed — skipped logging)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

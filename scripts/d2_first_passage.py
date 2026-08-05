"""Walk-forward evaluation of first-passage crossing probabilities (D2).

The served D2 decision layer is a binary alert: persistence forecast below the
25.0 threshold or not. This script evaluates the probabilistic alternative
built in `vine.d2_irrigation.first_passage`: keep the random walk, forecast
the probability that the observed series crosses below the threshold within
(t, t+h]. Scored with Brier score and log loss against two references scored
identically, the binary persistence alert read as probability 0 or 1, and the
training-fold base rate as a constant probability.

    uv run python scripts/d2_first_passage.py
    uv run python scripts/d2_first_passage.py configs/d2_irrigation/first_passage.yaml --no-mlflow

Same purged expanding walk-forward folds as the existing D2 harness. Outcome
windows must be fully observed; windows containing gaps are skipped. Writes
deterministic CSVs to docs/reports/assets/ and logs to MLflow.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import BaseModel

from vine.common.config import load_config
from vine.common.seed import seed_everything
from vine.d2_irrigation.data import load_soil_probe_frames
from vine.d2_irrigation.first_passage import (
    crossing_probability,
    ewma_drift_series,
    ewma_volatility_series,
)
from vine.d5_evaluation.walkforward import expanding_splits, purged_train_slice

ASSETS = Path("docs/reports/assets")
MODELS = ("first_passage_zero", "first_passage_ewma", "persistence_alert", "base_rate")
EPS = 1e-15  # log-loss clip, sklearn's default


class FirstPassageConfig(BaseModel):
    threshold: float = 25.0
    horizons_h: list[int] = [6, 12, 24, 48]
    n_folds: int = 5
    sigma_halflife_h: float = 72.0
    mu_halflife_h: float = 336.0
    min_pairs: int = 24


def crossing_labels(obs: np.ndarray, below: np.ndarray, h: int) -> tuple[np.ndarray, np.ndarray]:
    """Per decision index i: (window fully observed, crossed within (i, i+h])."""
    n = len(obs)
    co = np.concatenate([[0], np.cumsum(obs)])
    cb = np.concatenate([[0], np.cumsum(below)])
    evaluable = np.zeros(n, dtype=bool)
    crossed = np.zeros(n, dtype=bool)
    idx = np.arange(n - h)
    evaluable[idx] = obs[idx] & (co[idx + 1 + h] - co[idx + 1] == h)
    crossed[idx] = (cb[idx + 1 + h] - cb[idx + 1]) > 0
    return evaluable, crossed


def brier(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.mean((p - y) ** 2))


def log_loss(y: np.ndarray, p: np.ndarray) -> float:
    p = np.clip(p, EPS, 1 - EPS)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def evaluate_device(y: pd.Series, cfg: FirstPassageConfig) -> dict[int, dict[str, np.ndarray]]:
    """Holdout crossing labels + the four probability forecasts, per horizon."""
    values = y.to_numpy(dtype=float)
    obs = np.isfinite(values)
    below = obs & (np.nan_to_num(values, nan=np.inf) < cfg.threshold)
    sigma = ewma_volatility_series(y, cfg.sigma_halflife_h, cfg.min_pairs).to_numpy(dtype=float)
    mu = ewma_drift_series(y, cfg.mu_halflife_h, cfg.min_pairs).to_numpy(dtype=float)
    splits = expanding_splits(len(y), cfg.n_folds)

    out: dict[int, dict[str, np.ndarray]] = {}
    for h in cfg.horizons_h:
        evaluable, crossed = crossing_labels(obs, below, h)
        scorable = evaluable & np.isfinite(sigma) & np.isfinite(mu)
        ys, preds = [], {m: [] for m in MODELS}
        for tr, te in splits:
            purged = purged_train_slice(tr, h - 1)
            train_eval = evaluable[: purged.stop]
            rate = float(crossed[: purged.stop][train_eval].mean()) if train_eval.any() else 0.5
            for i in range(te.start, te.stop):
                if not scorable[i]:
                    continue
                ys.append(float(crossed[i]))
                preds["first_passage_zero"].append(
                    crossing_probability(values[i], cfg.threshold, h, 0.0, sigma[i])
                )
                preds["first_passage_ewma"].append(
                    crossing_probability(values[i], cfg.threshold, h, mu[i], sigma[i])
                )
                preds["persistence_alert"].append(1.0 if below[i] else 0.0)
                preds["base_rate"].append(rate)
        out[h] = {"y": np.array(ys), **{m: np.array(p) for m, p in preds.items()}}
    return out


def reliability_rows(pooled: dict[int, dict[str, np.ndarray]], horizons: list[int]) -> list[dict]:
    """Predicted-probability deciles vs observed crossing frequency."""
    rows = []
    for model in ("first_passage_zero", "first_passage_ewma"):
        for h in horizons:
            y, p = pooled[h]["y"], pooled[h][model]
            bins = np.minimum((p * 10).astype(int), 9)
            for b in range(10):
                m = bins == b
                if not m.any():
                    continue
                rows.append(
                    {
                        "model": model,
                        "horizon_h": h,
                        "bin": f"{b / 10:.1f} to {(b + 1) / 10:.1f}",
                        "n": int(m.sum()),
                        "p_mean": float(p[m].mean()),
                        "obs_rate": float(y[m].mean()),
                    }
                )
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "config",
        nargs="?",
        default="configs/d2_irrigation/first_passage.yaml",
        help="YAML experiment config",
    )
    ap.add_argument("--no-mlflow", action="store_true")
    args = ap.parse_args()

    cfg = FirstPassageConfig(**load_config(Path(args.config)))
    seed = seed_everything()

    print("loading soil probes...")
    frames = load_soil_probe_frames()
    per_device = {}
    for device, frame in frames.items():
        per_device[device] = evaluate_device(frame["soil_water"], cfg)
        counts = {h: int(per_device[device][h]["y"].sum()) for h in cfg.horizons_h}
        print(f"  {device}: crossings per horizon {counts}")

    # Pool every probe's scored rows for the ALL block + reliability table.
    pooled = {
        h: {k: np.concatenate([per_device[d][h][k] for d in per_device]) for k in ("y", *MODELS)}
        for h in cfg.horizons_h
    }

    rows = []
    for device, res in {**per_device, "ALL": pooled}.items():
        for h in cfg.horizons_h:
            y = res[h]["y"]
            if len(y) == 0:
                continue
            for model in MODELS:
                p = res[h][model]
                rows.append(
                    {
                        "device": device,
                        "model": model,
                        "horizon_h": h,
                        "n": len(y),
                        "n_cross": int(y.sum()),
                        "brier": brier(y, p),
                        "log_loss": log_loss(y, p),
                    }
                )
    results = (
        pd.DataFrame(rows).sort_values(["horizon_h", "device", "model"]).reset_index(drop=True)
    )
    reliability = pd.DataFrame(reliability_rows(pooled, cfg.horizons_h))

    print("\n" + results.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print("\nreliability (pooled across probes):")
    print(reliability.to_string(index=False, float_format=lambda v: f"{v:.3f}"))

    ASSETS.mkdir(parents=True, exist_ok=True)
    results.to_csv(ASSETS / "d2_first_passage_results.csv", index=False, float_format="%.6f")
    reliability.to_csv(
        ASSETS / "d2_first_passage_reliability.csv", index=False, float_format="%.6f"
    )
    print(f"\nwrote {ASSETS}/d2_first_passage_results.csv and d2_first_passage_reliability.csv")

    if not args.no_mlflow:
        try:
            import mlflow

            mlflow.set_experiment("d2_irrigation")
            with mlflow.start_run(run_name="first-passage") as run:
                mlflow.log_params({**cfg.model_dump(), "seed": seed, "sensors": list(frames)})
                for r in results.itertuples():
                    tag = f"{r.device}_{r.model}_{r.horizon_h}h"
                    mlflow.log_metric(f"brier_{tag}", r.brier)
                    mlflow.log_metric(f"logloss_{tag}", r.log_loss)
                print(f"mlflow run: {run.info.run_id}")
        except ImportError:
            print("\n(mlflow not installed, skipped logging)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

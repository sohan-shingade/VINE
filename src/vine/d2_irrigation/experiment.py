"""Run one config-driven D2 experiment: walk-forward eval of forecasts vs baselines.

Takes the D1 feature frame (already built — this module never touches the
network) and a validated `IrrigationConfig`, and produces one tidy results
table: per (model, horizon) the forecast error, the skill vs persistence, and
the precision/recall of the irrigation decision it implies. Every model —
baseline or learned — is scored on exactly the same rows, so the comparison
is fair by construction (ADR-0003).

Alignment convention: row `t` holds the prediction *for* time `t`, made
`horizon` rows earlier. Baselines are then pure shifts of the target, and
learned models see `frame.shift(horizon)` — the features as they were at
decision time.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from vine.common.logging import get_logger
from vine.d1_pipeline.pipeline import add_lead_time_features
from vine.d2_irrigation import baselines
from vine.d2_irrigation.config import IrrigationConfig
from vine.d2_irrigation.models import make_arima, make_ridge
from vine.d5_evaluation.metrics import mae, precision_recall, rmse
from vine.d5_evaluation.walkforward import expanding_splits, skill, walk_forward

log = get_logger(__name__)

# Matches the horizon out of a `{stem}_next_{h}h` lead-time column name (see
# `vine.d1_pipeline.pipeline.add_lead_time_features`).
_NEXT_H_RE = re.compile(r"_next_(\d+)h$")


def run_experiment(frame: pd.DataFrame, cfg: IrrigationConfig) -> pd.DataFrame:
    """Evaluate the configured model + all baselines, walk-forward, per horizon.

    Args:
        frame: D1 feature frame on a regular hourly grid (see
            `build_sensor_features` / `attach_weather`), containing `cfg.target`.
        cfg: the experiment config (a run = config + seed).

    Returns:
        Tidy frame: model, horizon_h, n, mae, rmse, skill_vs_persistence,
        precision, recall — sorted by horizon then MAE.
    """
    if cfg.forecast_features:
        frame = add_lead_time_features(frame, cfg.horizons_h)

    y = frame[cfg.target]
    numeric = frame.select_dtypes("number")

    rows = []
    for h in cfg.horizons_h:
        # Features as known at decision time t-h, aligned to target time t.
        X = numeric.shift(h)
        # A `_next_{h_feat}h` column read at decision time t-h covers
        # (t-h, t-h+h_feat]; that only equals the target window (t-h, t] when
        # h_feat == h. Any other horizon reaches past (or short of) the target
        # time t — a mismatched one is a genuine future leak, not a feature.
        mismatched = [c for c in X.columns if (m := _NEXT_H_RE.search(c)) and int(m.group(1)) != h]
        X = X.drop(columns=mismatched)
        preds: dict[str, pd.Series] = {
            "persistence": baselines.naive_persistence(y, h),
            "seasonal_naive": baselines.seasonal_naive(y, h),
            "climatology": walk_forward(
                X,
                y,
                lambda X_tr, y_tr, X_te: baselines.climatology_hourly(y_tr, X_te.index),
                cfg.n_folds,
            ),
        }
        if cfg.model == "ridge" and cfg.predict_delta:
            # Learn the change y(t) - y(t-h) instead of the level: persistence
            # is then exactly the zero-change prediction, so any learned skill
            # is real signal, not just re-deriving persistence with error.
            delta = y - y.shift(h)
            delta_pred = walk_forward(X, delta, make_ridge(cfg.alpha), cfg.n_folds)
            preds["ridge_delta"] = y.shift(h) + delta_pred  # reconstruct to level to score fairly
        elif cfg.model == "ridge":
            preds["ridge"] = walk_forward(X, y, make_ridge(cfg.alpha), cfg.n_folds)
        elif cfg.model == "arima":
            p, d, q = cfg.order
            preds["arima"] = walk_forward(
                X, y, make_arima((p, d, q), horizon=h, target_col=cfg.target), cfg.n_folds
            )

        # Score every model on the same rows: holdout region, all preds + truth present.
        holdout_start = expanding_splits(len(y), cfg.n_folds)[0][1].start
        valid = y.notna()
        for p in preds.values():
            valid &= p.notna()
        valid.iloc[:holdout_start] = False
        n = int(valid.sum())
        if n == 0:
            raise ValueError(f"horizon {h}h: no scorable rows (all-gap holdout?)")

        # Per-fold skills alongside the aggregate: a pooled MAE over
        # heterogeneous folds can be dominated by one easy/hard stretch (the
        # eval review caught exactly that), so the ship gate reads the spread.
        splits = expanding_splits(len(y), cfg.n_folds)
        fold_masks = []
        for _, te in splits:
            m = valid.copy()
            m.iloc[: te.start] = False
            m.iloc[te.stop :] = False
            if m.any():
                fold_masks.append(m)

        yt = y[valid].to_numpy()
        pers = preds["persistence"]
        for name, p in preds.items():
            yp = p[valid].to_numpy()
            prec, rec = precision_recall(yt < cfg.irrigate_below, yp < cfg.irrigate_below)
            fold_skills = [
                skill(
                    mae(y[m].to_numpy(), p[m].to_numpy()),
                    mae(y[m].to_numpy(), pers[m].to_numpy()),
                )
                for m in fold_masks
            ]
            rows.append(
                {
                    "model": name,
                    "horizon_h": h,
                    "n": n,
                    "mae": mae(yt, yp),
                    "rmse": rmse(yt, yp),
                    "precision": prec,
                    "recall": rec,
                    "skill_fold_median": float(np.median(fold_skills)),
                    "skill_fold_min": float(np.min(fold_skills)),
                }
            )
        log.info("evaluated horizon", horizon_h=h, n=n, models=list(preds))

    results = pd.DataFrame(rows)
    persistence_mae = results[results["model"] == "persistence"].set_index("horizon_h")["mae"]
    results["skill_vs_persistence"] = [
        skill(r.mae, persistence_mae[r.horizon_h]) for r in results.itertuples()
    ]
    return results.sort_values(["horizon_h", "mae"]).reset_index(drop=True)


def log_to_mlflow(cfg: IrrigationConfig, results: pd.DataFrame, seed: int) -> None:
    """Record the run in MLflow (local `mlruns/` unless MLFLOW_TRACKING_URI is set).

    No-op with a warning when the `track` extra isn't installed — the results
    table is still returned/printed either way.
    """
    try:
        import mlflow
    except ImportError:
        log.warning("mlflow not installed (track extra) — skipping experiment logging")
        return

    mlflow.set_experiment("d2_irrigation")
    with mlflow.start_run(run_name=f"{cfg.model}-{cfg.device}"):
        mlflow.log_params({**cfg.model_dump(), "seed": seed})
        for r in results.itertuples():
            mlflow.log_metric(f"mae_{r.model}_{r.horizon_h}h", r.mae)
            mlflow.log_metric(f"skill_{r.model}_{r.horizon_h}h", r.skill_vs_persistence)

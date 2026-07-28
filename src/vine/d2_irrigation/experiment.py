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

import numpy as np
import pandas as pd

from vine.common.logging import get_logger
from vine.d1_pipeline.pipeline import add_lead_time_features
from vine.d2_irrigation import baselines
from vine.d2_irrigation.config import IrrigationConfig
from vine.d2_irrigation.models import (
    make_arima,
    make_forest,
    make_gbt,
    make_ridge,
    make_water_balance,
)
from vine.d5_evaluation.metrics import mae, precision_recall, rmse
from vine.d5_evaluation.walkforward import expanding_splits, skill, walk_forward

log = get_logger(__name__)

# Matches the horizon out of a `{stem}_next_{h}h` lead-time column name (see
# `vine.d1_pipeline.pipeline.add_lead_time_features`).


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
        # The YAML declaration is the feature contract. Sensor-derived columns
        # may include engineered suffixes from a declared base feature; incidental
        # numeric columns, including realized daily weather, are excluded.
        feature_columns = [
            column
            for column in numeric.columns
            if any(
                column == feature or column.startswith(f"{feature}_") for feature in cfg.features
            )
        ]
        if cfg.forecast_features:
            feature_columns.extend(
                column
                for column in (f"et0_next_{h}h", f"precip_next_{h}h")
                if column in numeric.columns and column not in feature_columns
            )
        if not feature_columns:
            raise ValueError(f"horizon {h}h: no declared numeric features are available")

        # Features as known at decision time t-h, aligned to target time t.
        X = numeric[feature_columns].shift(h)
        preds: dict[str, pd.Series] = {
            "persistence": baselines.naive_persistence(y, h),
            "drydown": baselines.drydown_trend(y, h),
            "seasonal_naive": baselines.seasonal_naive(y, h),
            "climatology": walk_forward(
                X,
                y,
                lambda X_tr, y_tr, X_te: baselines.climatology_hourly(y_tr, X_te.index),
                cfg.n_folds,
                purge=h - 1,
            ),
        }
        regressors = {
            "ridge": lambda: make_ridge(cfg.alpha),
            "forest": lambda: make_forest(cfg.n_estimators, cfg.max_depth),
            "gbt": lambda: make_gbt(cfg.gbt_learning_rate, cfg.gbt_max_iter),
        }
        if cfg.model in regressors and cfg.predict_delta:
            # Learn the change y(t) - y(t-h) instead of the level: persistence
            # is then exactly the zero-change prediction, so any learned skill
            # is real signal, not just re-deriving persistence with error.
            delta = y - y.shift(h)
            delta_pred = walk_forward(X, delta, regressors[cfg.model](), cfg.n_folds, purge=h - 1)
            # reconstruct to level to score fairly
            preds[f"{cfg.model}_delta"] = y.shift(h) + delta_pred
        elif cfg.model in regressors:
            preds[cfg.model] = walk_forward(X, y, regressors[cfg.model](), cfg.n_folds, purge=h - 1)
        elif cfg.model == "arima":
            p, d, q = cfg.order
            preds["arima"] = walk_forward(
                X,
                y,
                make_arima((p, d, q), horizon=h, target_col=cfg.target),
                cfg.n_folds,
                purge=h - 1,
            )
        elif cfg.model == "water_balance":
            preds["water_balance"] = walk_forward(
                X,
                y,
                make_water_balance(
                    cfg.target,
                    horizon=h,
                    use_level=cfg.wb_use_level,
                    gate_precip_mm=cfg.wb_gate_precip_mm,
                    robust=cfg.wb_robust,
                    saturate_k=cfg.wb_saturate_k,
                    adaptive_blend=cfg.wb_adaptive_blend,
                    val_frac=cfg.wb_val_frac,
                    blend_weights=cfg.wb_blend_weights,
                    min_fit_rows=cfg.wb_min_fit_rows,
                    min_val_rows=cfg.wb_min_val_rows,
                    huber_max_iter=cfg.wb_huber_max_iter,
                ),
                cfg.n_folds,
                purge=h - 1,
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

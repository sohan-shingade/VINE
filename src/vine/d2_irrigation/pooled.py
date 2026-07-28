"""Global (pooled) cross-sensor soil-moisture forecaster (D2).

The per-sensor ladder — ridge, ARIMA, forest, GBT — all failed to beat
persistence on real data (ADR-0003). But the forecasting literature is
consistent about *why* learned models sometimes beat naive baselines: not from
more history on one series, but from **cross-learning across many related
series** (the M4 winner trained globally across all series; M5's pure-ML
sweep came on ~42k related retail series; Elsayed et al. 2021 show a windowed
GBT matching deep nets when it can pool). IHV has five near-identical soil
probes in one vineyard sharing one weather stream — the textbook setting to
test that lever, and the one rung we had not yet tried.

This module fits ONE model on every sensor's rows at once and scores each
sensor against its OWN persistence baseline, under the same causal walk-forward
as every other D2 rung. Two deliberate choices give pooling its fair shot:

- **Δ-target**: learn `y(t) - y(t-h)`, reconstruct the level per sensor before
  scoring. The probes sit at different absolute moisture levels; pooling on the
  change (not the level) puts every sensor on a comparable scale so the model
  spends capacity on dynamics, not per-sensor offsets. Persistence is then the
  zero-change prediction, so any skill is real signal (same argument as
  `experiment.predict_delta`).
- **Time-aligned folds**: folds are cut on a shared hourly timeline, so a fold's
  training rows never include a timestamp from any sensor's test window — the
  pooled analogue of the single-series causal split.

Pure pandas/numpy + sklearn; I/O (snapshot loading) stays in the runner.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from vine.d2_irrigation import baselines
from vine.d2_irrigation.config import IrrigationConfig
from vine.d5_evaluation.metrics import mae, precision_recall, rmse
from vine.d5_evaluation.walkforward import expanding_splits, purged_train_slice, skill


def align_frames(frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Reindex every sensor's feature frame onto one shared hourly grid.

    Each sensor is regularized independently upstream, so their indices differ
    by a few boundary hours. Pooling needs position `i` to mean the same
    timestamp for every sensor, so we reindex all frames to the union of their
    indices (missing hours become NaN rows — flagged gaps, masked in scoring).
    """
    if not frames:
        raise ValueError("no frames to align")
    common = frames[next(iter(frames))].index
    for f in frames.values():
        common = common.union(f.index)
    return {name: f.reindex(common) for name, f in frames.items()}


def _feature_columns(
    frames: dict[str, pd.DataFrame], cfg: IrrigationConfig, horizon: int
) -> list[str]:
    """Shared, declared predictors for one horizon.

    Sensor-derived columns must belong to a base feature named in the YAML.
    Lead-time weather is opt-in and only the matching horizon is causal for the
    target window. This keeps the config—not incidental numeric columns—the
    source of truth for what the pooled model sees.
    """
    devices = list(frames)
    shared = set.intersection(*(set(frames[d].columns) for d in devices))
    ordered = [c for c in frames[devices[0]].columns if c in shared]
    declared = [
        c
        for c in ordered
        if any(c == feature or c.startswith(f"{feature}_") for feature in cfg.features)
    ]
    if cfg.forecast_features:
        declared.extend(
            c
            for c in (f"et0_next_{horizon}h", f"precip_next_{horizon}h")
            if c in shared and c not in declared
        )
    return declared


def _estimator(cfg: IrrigationConfig):
    """Fresh sklearn regressor for a pooled ridge, GBT, or forest fit."""
    if cfg.model == "ridge":
        from sklearn.linear_model import Ridge
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler

        return make_pipeline(StandardScaler(), Ridge(alpha=cfg.alpha))
    if cfg.model == "gbt":
        from sklearn.ensemble import HistGradientBoostingRegressor

        return HistGradientBoostingRegressor(
            learning_rate=cfg.gbt_learning_rate, max_iter=cfg.gbt_max_iter, random_state=0
        )
    if cfg.model == "forest":
        from sklearn.ensemble import RandomForestRegressor

        return RandomForestRegressor(
            n_estimators=cfg.n_estimators, max_depth=cfg.max_depth, random_state=0, n_jobs=-1
        )
    raise ValueError(f"pooled model must be ridge | gbt | forest, got {cfg.model!r}")


def _fit_predict_pooled(
    cfg: IrrigationConfig,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_tests: dict[str, pd.DataFrame],
) -> dict[str, np.ndarray]:
    """Fit one estimator on stacked training rows, predict each sensor's test rows.

    Ridge/forest need complete rows (drop no-signal cols, then rows with any
    NaN feature or target); GBT handles NaN features natively and only needs a
    finite target. Mirrors the per-sensor `models.py` policy so the comparison
    is apples-to-apples — the only change is that one fit serves all sensors.
    """
    cols = X_train.columns[X_train.notna().any()]
    out = {name: np.full(len(Xte), np.nan) for name, Xte in X_tests.items()}
    if not len(cols):
        return out
    est = _estimator(cfg)
    tolerant = cfg.model == "gbt"  # native NaN handling
    # GBT routes NaN features down a learned branch, so it only needs a finite
    # target; ridge/forest need every feature present (complete rows only).
    ok = y_train.notna() if tolerant else X_train[cols].notna().all(axis=1) & y_train.notna()
    if int(ok.sum()) < 20:
        return out
    est.fit(X_train.loc[ok, cols], y_train[ok])

    out = {}
    for name, Xte in X_tests.items():
        pred = np.full(len(Xte), np.nan)
        if tolerant:
            pred = np.asarray(est.predict(Xte[cols]), dtype=float)
        else:
            te = Xte[cols].notna().all(axis=1).to_numpy()
            if te.any():
                pred[te] = est.predict(Xte.loc[te, cols])
        out[name] = pred
    return out


def run_pooled_experiment(frames: dict[str, pd.DataFrame], cfg: IrrigationConfig) -> pd.DataFrame:
    """Walk-forward evaluate one pooled model across sensors, per horizon.

    Args:
        frames: {device -> D1 feature frame} on (near-)regular hourly grids, each
            containing `cfg.target`. Aligned onto a shared grid internally.
        cfg: experiment config; `cfg.model` selects the pooled regressor. The
            pooled fit always learns the Δ-target (see module docstring), so
            `cfg.predict_delta` is implied and need not be set.

    Returns:
        Tidy frame: device, model, horizon_h, n, mae, rmse, skill_vs_persistence,
        skill_fold_median, skill_fold_min, precision, recall. One block per
        device (its own persistence + the pooled model), plus an `ALL` block
        pooling every sensor's scored rows together.
    """
    if cfg.model not in {"ridge", "gbt", "forest"}:
        raise ValueError("pooled experiment supports ridge | gbt | forest")
    if cfg.forecast_features:
        from vine.d1_pipeline.pipeline import add_lead_time_features

        frames = {d: add_lead_time_features(f, cfg.horizons_h) for d, f in frames.items()}
    frames = align_frames(frames)
    devices = list(frames)
    index = frames[devices[0]].index
    n = len(index)

    rows: list[dict] = []
    # Accumulate every device's scored (truth, pooled-pred, persistence-pred) so
    # an ALL row can report the pooled model's skill over the whole sensor fleet.
    agg: dict[int, dict[str, list[np.ndarray]]] = {
        h: {"y": [], "pool": [], "pers": []} for h in cfg.horizons_h
    }

    for h in cfg.horizons_h:
        splits = expanding_splits(n, cfg.n_folds)
        holdout_start = splits[0][1].start
        fold_agg: list[dict[str, list[np.ndarray]]] = [
            {"y": [], "pool": [], "pers": []} for _ in splits
        ]

        # Per device: features known at t-h (shift h), target, Δ-target, persistence.
        Xs, ys, deltas, pers = {}, {}, {}, {}
        for d in devices:
            numeric = frames[d].select_dtypes("number")
            Xs[d] = numeric.shift(h)
            ys[d] = frames[d][cfg.target]
            deltas[d] = ys[d] - ys[d].shift(h)
            pers[d] = baselines.naive_persistence(ys[d], h)

        # The YAML-declared predictors shared by every sensor. The matching
        # lead-time weather pair is included only when forecast features are on.
        cols = _feature_columns(Xs, cfg, h)
        if not cols:
            raise ValueError(f"horizon {h}h: no declared features shared by every sensor")

        pooled_pred = {d: pd.Series(np.nan, index=index, dtype=float) for d in devices}
        for tr, te in splits:
            train = purged_train_slice(tr, h - 1)
            X_train = pd.concat([Xs[d][cols].iloc[train] for d in devices], ignore_index=True)
            y_train = pd.concat([deltas[d].iloc[train] for d in devices], ignore_index=True)
            X_tests = {d: Xs[d][cols].iloc[te] for d in devices}
            dpred = _fit_predict_pooled(cfg, X_train, y_train, X_tests)
            for d in devices:
                # reconstruct level: last obs at decision time + predicted change
                level = ys[d].shift(h).iloc[te].to_numpy() + dpred[d]
                pooled_pred[d].iloc[te] = level

        # Score each device on rows where truth + pooled + persistence all exist.
        for d in devices:
            y = ys[d]
            valid = y.notna() & pooled_pred[d].notna() & pers[d].notna()
            valid.iloc[:holdout_start] = False
            nrows = int(valid.sum())
            if nrows == 0:
                continue

            fold_masks = []
            for fold_i, (_, te) in enumerate(splits):
                m = valid.copy()
                m.iloc[: te.start] = False
                m.iloc[te.stop :] = False
                if m.any():
                    fold_masks.append(m)
                    fold_agg[fold_i]["y"].append(y[m].to_numpy())
                    fold_agg[fold_i]["pool"].append(pooled_pred[d][m].to_numpy())
                    fold_agg[fold_i]["pers"].append(pers[d][m].to_numpy())

            yt = y[valid].to_numpy()
            pp = pooled_pred[d][valid].to_numpy()
            pv = pers[d][valid].to_numpy()
            agg[h]["y"].append(yt)
            agg[h]["pool"].append(pp)
            agg[h]["pers"].append(pv)

            for name, pred in ((f"pooled_{cfg.model}", pp), ("persistence", pv)):
                fold_skills = [
                    skill(
                        mae(y[m].to_numpy(), _sel(pred, valid, m)),
                        mae(y[m].to_numpy(), _sel(pv, valid, m)),
                    )
                    for m in fold_masks
                ]
                prec, rec = precision_recall(yt < cfg.irrigate_below, pred < cfg.irrigate_below)
                rows.append(
                    {
                        "device": d,
                        "model": name,
                        "horizon_h": h,
                        "n": nrows,
                        "mae": mae(yt, pred),
                        "rmse": rmse(yt, pred),
                        "skill_vs_persistence": skill(mae(yt, pred), mae(yt, pv)),
                        "skill_fold_median": float(np.median(fold_skills))
                        if fold_skills
                        else np.nan,
                        "skill_fold_min": float(np.min(fold_skills)) if fold_skills else np.nan,
                        "precision": prec,
                        "recall": rec,
                    }
                )

        # Fleet-wide (ALL) rows: pool every device's scored rows together.
        if agg[h]["y"]:
            yt = np.concatenate(agg[h]["y"])
            pp = np.concatenate(agg[h]["pool"])
            pv = np.concatenate(agg[h]["pers"])
            fleet_fold_skills = []
            for fold in fold_agg:
                if fold["y"]:
                    fy = np.concatenate(fold["y"])
                    fp = np.concatenate(fold["pool"])
                    fv = np.concatenate(fold["pers"])
                    fleet_fold_skills.append(skill(mae(fy, fp), mae(fy, fv)))
            for name, pred in ((f"pooled_{cfg.model}", pp), ("persistence", pv)):
                fold_skills = (
                    fleet_fold_skills
                    if name.startswith("pooled_")
                    else [0.0] * len(fleet_fold_skills)
                )
                prec, rec = precision_recall(yt < cfg.irrigate_below, pred < cfg.irrigate_below)
                rows.append(
                    {
                        "device": "ALL",
                        "model": name,
                        "horizon_h": h,
                        "n": len(yt),
                        "mae": mae(yt, pred),
                        "rmse": rmse(yt, pred),
                        "skill_vs_persistence": skill(mae(yt, pred), mae(yt, pv)),
                        "skill_fold_median": float(np.median(fold_skills))
                        if fold_skills
                        else np.nan,
                        "skill_fold_min": float(np.min(fold_skills)) if fold_skills else np.nan,
                        "precision": prec,
                        "recall": rec,
                    }
                )

    if not rows:
        return pd.DataFrame(
            columns=[
                "device",
                "model",
                "horizon_h",
                "n",
                "mae",
                "rmse",
                "skill_vs_persistence",
                "skill_fold_median",
                "skill_fold_min",
                "precision",
                "recall",
            ]
        )
    return pd.DataFrame(rows).sort_values(["horizon_h", "device", "mae"]).reset_index(drop=True)


def _sel(full_valid_array: np.ndarray, valid: pd.Series, mask: pd.Series) -> np.ndarray:
    """Select this-fold entries out of an array indexed like `valid`'s True rows."""
    # full_valid_array is aligned to valid[valid]; pick the positions where mask is True.
    sub = mask[valid].to_numpy()
    return full_valid_array[sub]

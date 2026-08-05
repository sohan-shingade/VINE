"""Event-conditioned evaluation of D2 forecasts (D2, event study).

Aggregate MAE over the roughly 1,350-hour holdout is dominated by quiet
drydown hours where persistence is nearly exact. The hours that decide
whether a challenger is useful are the rare ones: rain fronts and irrigation
jumps, plus the drainage transient that follows either. This module scores
retained per-timestamp walk-forward forecasts separately on event windows
(a detected rise event plus a trailing drainage tail) and on quiet hours,
and reports what fraction of persistence's total absolute error falls inside
the event windows.

Pure pandas, no I/O. The runner `scripts/d2_event_study.py` loads snapshots,
detects events, and logs to MLflow.
"""

from __future__ import annotations

import pandas as pd

from vine.d2_irrigation import baselines
from vine.d2_irrigation.config import IrrigationConfig
from vine.d5_evaluation.metrics import mae, rmse
from vine.d5_evaluation.walkforward import expanding_splits, skill, walk_forward

SUBSETS = ("event", "quiet", "all")


def event_mask(index: pd.DatetimeIndex, events: pd.DataFrame, *, trailing_h: int = 24) -> pd.Series:
    """Mark target timestamps that fall inside any event window.

    A timestamp t is inside an event window when start <= t <= end plus
    `trailing_h` hours. The trailing tail captures the post-jump drainage
    transient, where the level is still moving fast and persistence from a
    pre-jump or mid-jump origin is stale. Overlapping windows union.

    Args:
        index: target timestamps of the evaluation grid.
        events: frame from `detect_rise_events` with `start` and `end` columns.
        trailing_h: hours appended after each event's `end`.

    Returns:
        Boolean series on `index`: True inside an event window.
    """
    mask = pd.Series(False, index=index)
    trail = pd.Timedelta(hours=trailing_h)
    for event in events.itertuples():
        mask |= (index >= event.start) & (index <= event.end + trail)
    return mask


def subset_metrics(
    y: pd.Series,
    preds: dict[str, pd.Series],
    in_event: pd.Series,
    valid: pd.Series,
) -> pd.DataFrame:
    """Score every model on the event, quiet, and full subsets of the valid rows.

    Skill is computed against persistence's MAE on the same subset, so a
    challenger earns event-subset skill only by beating persistence on event
    hours themselves. `preds` must contain a "persistence" entry. An empty
    subset yields n=0 with NaN metrics rather than an error.

    Args:
        y: target series.
        preds: per-timestamp predictions keyed by model name.
        in_event: boolean event mask on `y.index` (see `event_mask`).
        valid: boolean mask of scorable rows (holdout, truth and all preds present).

    Returns:
        Tidy frame: model, subset, n, mae, rmse, skill_vs_persistence.
    """
    masks = {"event": valid & in_event, "quiet": valid & ~in_event, "all": valid}
    rows = []
    for subset, mask in masks.items():
        n = int(mask.sum())
        yt = y[mask].to_numpy()
        base = mae(yt, preds["persistence"][mask].to_numpy()) if n else float("nan")
        for name, pred in preds.items():
            if n == 0:
                rows.append(
                    {
                        "model": name,
                        "subset": subset,
                        "n": 0,
                        "mae": float("nan"),
                        "rmse": float("nan"),
                        "skill_vs_persistence": float("nan"),
                    }
                )
                continue
            yp = pred[mask].to_numpy()
            model_mae = mae(yt, yp)
            rows.append(
                {
                    "model": name,
                    "subset": subset,
                    "n": n,
                    "mae": model_mae,
                    "rmse": rmse(yt, yp),
                    "skill_vs_persistence": skill(model_mae, base),
                }
            )
    return pd.DataFrame(rows)


def event_error_share(
    y: pd.Series, pers: pd.Series, in_event: pd.Series, valid: pd.Series
) -> float:
    """Fraction of persistence's total absolute error that falls on event hours.

    This is the dilution number: if a small share of hours carries a large
    share of persistence's L1 error, aggregate MAE understates how bad the
    baseline is exactly where forecasts matter.
    """
    err = (y - pers).abs()
    total = float(err[valid].sum())
    if total == 0.0:
        return 0.0
    return float(err[valid & in_event].sum() / total)


def run_event_study(
    frame: pd.DataFrame,
    cfg: IrrigationConfig,
    events: pd.DataFrame,
    vintages: pd.DataFrame | None = None,
    trailing_h: int = 24,
) -> tuple[pd.DataFrame, dict[int, float]]:
    """Walk-forward evaluate one probe with predictions retained per timestamp.

    Reuses the shared purged walk-forward machinery (expanding folds, h minus 1
    label purge) but keeps every model's per-timestamp predictions so they can
    be split by the event mask afterward. Models: persistence, diurnal drift,
    and additionally water balance when `cfg.model == "water_balance"`.

    Args:
        frame: D1 feature frame for one probe (regular hourly grid).
        cfg: experiment config; `horizons_h`, `n_folds`, and the water-balance
            knobs mirror the earlier experiments.
        events: detected rise events for this probe (`detect_rise_events`).
        vintages: archived-forecast frame, required for `weather_source: vintage`.
        trailing_h: drainage tail appended to each event window.

    Returns:
        Tuple of (tidy results frame: model, horizon_h, subset, n, mae, rmse,
        skill_vs_persistence; and per-horizon persistence event error share).
    """
    from vine.d1_pipeline.pipeline import add_lead_time_features, add_vintage_lead_time_features
    from vine.d2_irrigation.experiment import _diurnal_fit_predict
    from vine.d2_irrigation.models import make_water_balance

    if cfg.forecast_features:
        if cfg.weather_source == "vintage":
            if vintages is None:
                raise ValueError("weather_source 'vintage' requires a vintages frame")
            frame = add_vintage_lead_time_features(frame, cfg.horizons_h, vintages)
        else:
            frame = add_lead_time_features(frame, cfg.horizons_h)

    y = frame[cfg.target]
    numeric = frame.select_dtypes("number")
    in_event = event_mask(y.index, events, trailing_h=trailing_h)

    tables = []
    shares: dict[int, float] = {}
    for h in cfg.horizons_h:
        # Same declared-feature contract as `run_experiment`.
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

        X = numeric[feature_columns].shift(h)
        pers = baselines.naive_persistence(y, h)
        preds: dict[str, pd.Series] = {
            "persistence": pers,
            "diurnal_drift": walk_forward(
                X, y, _diurnal_fit_predict(pers, h), cfg.n_folds, purge=h - 1
            ),
        }
        if cfg.model == "water_balance":
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
        if not valid.any():
            raise ValueError(f"horizon {h}h: no scorable rows (all-gap holdout?)")

        table = subset_metrics(y, preds, in_event, valid)
        table.insert(1, "horizon_h", h)
        tables.append(table)
        shares[h] = event_error_share(y, pers, in_event, valid)
    return pd.concat(tables, ignore_index=True), shares

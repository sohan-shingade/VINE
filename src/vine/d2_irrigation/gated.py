"""Rain-gated persistence hybrid for soil moisture (D2).

The event study (`vine.d2_irrigation.event_study`) showed that the
water-balance correction under real archived forecast vintages beats
persistence on rain-event windows at 24 and 48 h, and that its aggregate
losses come from quiet hours where the correction fires with nothing
happening. This module builds the obvious hybrid: predict persistence by
default, and switch to the water-balance forecast only when the forecast
available at the origin predicts material rain over the horizon window. One
global gate threshold is chosen per walk-forward fold by nested, causal
selection on the training window alone.

Pure pandas plus the existing water-balance fit, no I/O. The runner
`scripts/d2_gated.py` loads snapshots, detects events, and logs to MLflow.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from vine.d2_irrigation import baselines
from vine.d2_irrigation.config import IrrigationConfig
from vine.d2_irrigation.event_study import event_mask, subset_metrics
from vine.d5_evaluation.metrics import mae, rmse
from vine.d5_evaluation.walkforward import (
    FitPredict,
    expanding_splits,
    purged_train_slice,
    skill,
)

THRESHOLDS_MM = (0.5, 1.0, 2.0, 5.0)

RESULT_COLUMNS = [
    "model",
    "horizon_h",
    "threshold_mm",
    "subset",
    "n",
    "mae",
    "rmse",
    "skill_vs_persistence",
    "skill_fold_min",
    "gate_fired_frac",
]


def gate_fired(forecast_precip: pd.Series, threshold_mm: float) -> pd.Series:
    """True where the origin-time forecast precip over the window reaches the threshold.

    `forecast_precip` is the `precip_next_{h}h` lead-time column already
    shifted to target time, so the value on the row for target time t is the
    precipitation the archived forecast at origin t-h predicted for the window
    (t-h, t]. A missing forecast never fires the gate: NaN comparisons are
    False, so the hybrid falls back to persistence exactly where forecast
    coverage is absent.

    Args:
        forecast_precip: forecast precip totals aligned to target timestamps.
        threshold_mm: gate threshold in millimetres over the horizon window.

    Returns:
        Boolean series on `forecast_precip.index`: True where the gate fires.
    """
    return forecast_precip >= threshold_mm


def hybrid_predict(pers: pd.Series, wb: pd.Series, fired: pd.Series) -> pd.Series:
    """Persistence by default, the water-balance forecast where the gate fired.

    Rows where the gate did not fire carry persistence's exact float values,
    never a recomputation. Where the gate fired and the water-balance forecast
    is unavailable (NaN), the hybrid emits persistence: the correction cannot
    be applied, so the default stands.

    Args:
        pers: persistence forecasts aligned to target timestamps.
        wb: water-balance forecasts on the same index (NaN where unavailable).
        fired: boolean gate decisions on the same index (see `gate_fired`).

    Returns:
        The hybrid forecast series on the shared index.
    """
    use_wb = fired & wb.notna()
    return pers.where(~use_wb, wb)


def select_threshold(
    X: pd.DataFrame,
    y: pd.Series,
    pers: pd.Series,
    wb_fit: FitPredict,
    train: slice,
    horizon: int,
    thresholds_mm: tuple[float, ...] = THRESHOLDS_MM,
    val_frac: float = 0.25,
    min_val_rows: int = 10,
) -> float:
    """Pick one global gate threshold using the fold's training window only.

    Nested, causal selection: the most recent `val_frac` of the training rows
    becomes an inner holdout, the water-balance correction is refit on the
    earlier rows with the same h minus 1 label purge at the inner boundary,
    and every candidate threshold scores the hybrid's MAE on the inner
    holdout. Smallest MAE wins; ties go to the largest threshold, which fires
    least and stays closest to the served persistence baseline. Too few
    scorable inner rows also returns the largest threshold. Nothing at or
    after `train.stop` is ever read.

    Args:
        X: decision-time feature frame aligned to target time (already shifted),
            containing the `precip_next_{h}h` gate column.
        y: target series.
        pers: persistence forecasts on `y.index`.
        wb_fit: the water-balance `fit_predict` for this horizon.
        train: the outer fold's training slice (positional, stop exclusive).
        horizon: forecast horizon in grid rows (hours).
        thresholds_mm: candidate gate thresholds.
        val_frac: fraction of the training rows held out for inner scoring.
        min_val_rows: minimum scorable inner rows to trust the selection.

    Returns:
        The selected threshold, always an element of `thresholds_mm`.
    """
    start = int(train.start or 0)
    stop = int(train.stop)
    cut = start + int((stop - start) * (1.0 - val_frac))
    inner_train = purged_train_slice(slice(start, cut), horizon - 1)

    wb_inner = pd.Series(np.nan, index=y.index, dtype=float)
    wb_inner.iloc[cut:stop] = wb_fit(X.iloc[inner_train], y.iloc[inner_train], X.iloc[cut:stop])

    mask = y.notna() & pers.notna()
    mask.iloc[:cut] = False
    mask.iloc[stop:] = False
    candidates = sorted(thresholds_mm, reverse=True)
    if int(mask.sum()) < min_val_rows:
        return candidates[0]

    forecast_precip = X[f"precip_next_{horizon}h"]
    yt = y[mask].to_numpy()
    best_threshold, best_err = candidates[0], float("inf")
    for threshold in candidates:
        pred = hybrid_predict(pers, wb_inner, gate_fired(forecast_precip, threshold))
        err = mae(yt, pred[mask].to_numpy())
        if err < best_err:
            best_threshold, best_err = threshold, err
    return best_threshold


def _score_mask(
    y: pd.Series, pred: pd.Series, pers: pd.Series, mask: pd.Series
) -> dict[str, float | int]:
    """Error metrics and skill vs persistence on one boolean row mask."""
    n = int(mask.sum())
    if n == 0:
        nan = float("nan")
        return {"n": 0, "mae": nan, "rmse": nan, "skill_vs_persistence": nan}
    yt = y[mask].to_numpy()
    model_mae = mae(yt, pred[mask].to_numpy())
    return {
        "n": n,
        "mae": model_mae,
        "rmse": rmse(yt, pred[mask].to_numpy()),
        "skill_vs_persistence": skill(model_mae, mae(yt, pers[mask].to_numpy())),
    }


def _fold_min_skill(
    y: pd.Series,
    pred: pd.Series,
    pers: pd.Series,
    fold_masks: list[pd.Series],
    subset_mask: pd.Series,
) -> float:
    """Worst per-fold skill vs persistence over the folds that touch the subset."""
    skills = []
    for fold_mask in fold_masks:
        m = fold_mask & subset_mask
        if m.any():
            skills.append(
                skill(
                    mae(y[m].to_numpy(), pred[m].to_numpy()),
                    mae(y[m].to_numpy(), pers[m].to_numpy()),
                )
            )
    return float(np.min(skills)) if skills else float("nan")


def run_gated(
    frame: pd.DataFrame,
    cfg: IrrigationConfig,
    events: pd.DataFrame,
    vintages: pd.DataFrame | None = None,
    thresholds_mm: tuple[float, ...] = THRESHOLDS_MM,
    trailing_h: int = 24,
    val_frac: float = 0.25,
) -> tuple[pd.DataFrame, dict[int, list[float]]]:
    """Walk-forward evaluate the rain-gated hybrid on one probe, per horizon.

    Reuses the shared purged walk-forward machinery (expanding folds, h minus 1
    label purge). The water-balance forecast is fit once per outer fold; the
    gate then combines it with persistence at every candidate threshold, plus
    a `gated_wb_selected` variant whose threshold is chosen per fold by
    `select_threshold` on the training window alone. Results are split by the
    event mask into event and quiet subsets alongside the full holdout, and
    additionally scored on the fired subset of each gated model.

    Args:
        frame: D1 feature frame for one probe (regular hourly grid).
        cfg: experiment config; the water-balance knobs mirror the vintage
            validation and `forecast_features` must be true.
        events: detected rise events for this probe (`detect_rise_events`).
        vintages: archived-forecast frame, required for `weather_source: vintage`.
        thresholds_mm: candidate gate thresholds, all reported in the output.
        trailing_h: drainage tail appended to each event window.
        val_frac: inner-holdout fraction for the per-fold threshold selection.

    Returns:
        Tuple of (tidy results frame with `RESULT_COLUMNS`, and the selected
        threshold per fold keyed by horizon).
    """
    from vine.d1_pipeline.pipeline import add_lead_time_features, add_vintage_lead_time_features
    from vine.d2_irrigation.models import make_water_balance

    if not cfg.forecast_features:
        raise ValueError("the gated hybrid requires forecast_features: true")
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
    selected_by_horizon: dict[int, list[float]] = {}
    for h in cfg.horizons_h:
        lead_columns = [f"et0_next_{h}h", f"precip_next_{h}h"]
        missing = [column for column in lead_columns if column not in numeric.columns]
        if missing:
            raise ValueError(f"horizon {h}h: missing lead-time columns {missing}")
        # Same declared-feature contract as `run_experiment` and the event study.
        feature_columns = [
            column
            for column in numeric.columns
            if any(
                column == feature or column.startswith(f"{feature}_") for feature in cfg.features
            )
        ]
        feature_columns.extend(column for column in lead_columns if column not in feature_columns)

        X = numeric[feature_columns].shift(h)
        pers = baselines.naive_persistence(y, h)
        wb_fit = make_water_balance(
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
        )

        splits = expanding_splits(len(y), cfg.n_folds)
        wb = pd.Series(np.nan, index=y.index, dtype=float)
        selected: list[float] = []
        for tr, te in splits:
            purged = purged_train_slice(tr, h - 1)
            wb.iloc[te] = wb_fit(X.iloc[purged], y.iloc[purged], X.iloc[te])
            selected.append(
                select_threshold(
                    X, y, pers, wb_fit, tr, h, thresholds_mm=thresholds_mm, val_frac=val_frac
                )
            )
        selected_by_horizon[h] = selected

        forecast_precip = X[f"precip_next_{h}h"]
        fired: dict[str, pd.Series] = {}
        preds: dict[str, pd.Series] = {"persistence": pers}
        for threshold in thresholds_mm:
            name = f"gated_wb_{threshold:g}"
            fired[name] = gate_fired(forecast_precip, threshold)
            preds[name] = hybrid_predict(pers, wb, fired[name])
        selected_pred = pd.Series(np.nan, index=y.index, dtype=float)
        selected_fired = pd.Series(False, index=y.index)
        for (_tr, te), threshold in zip(splits, selected, strict=True):
            fold_fired = gate_fired(forecast_precip, threshold)
            selected_pred.iloc[te] = hybrid_predict(pers, wb, fold_fired).iloc[te]
            selected_fired.iloc[te] = fold_fired.iloc[te]
        fired["gated_wb_selected"] = selected_fired
        preds["gated_wb_selected"] = selected_pred

        # Score every model on the same rows: holdout region, truth and all
        # preds present. The hybrid inherits persistence's row coverage, so the
        # scorable rowset matches the persistence baseline exactly.
        holdout_start = splits[0][1].start
        valid = y.notna()
        for p in preds.values():
            valid &= p.notna()
        valid.iloc[:holdout_start] = False
        if not valid.any():
            raise ValueError(f"horizon {h}h: no scorable rows (all-gap holdout?)")

        fold_masks = []
        for _, te in splits:
            m = valid.copy()
            m.iloc[: te.start] = False
            m.iloc[te.stop :] = False
            if m.any():
                fold_masks.append(m)

        table = subset_metrics(y, preds, in_event, valid)
        fired_rows = []
        for name, fired_mask in fired.items():
            row: dict[str, object] = {"model": name, "subset": "fired"}
            row.update(_score_mask(y, preds[name], pers, valid & fired_mask))
            fired_rows.append(row)
        table = pd.concat([table, pd.DataFrame(fired_rows)], ignore_index=True)

        subset_masks = {"event": valid & in_event, "quiet": valid & ~in_event, "all": valid}
        table["skill_fold_min"] = [
            _fold_min_skill(
                y,
                preds[str(r.model)],
                pers,
                fold_masks,
                subset_masks[str(r.subset)]
                if r.subset in subset_masks
                else valid & fired[str(r.model)],
            )
            for r in table.itertuples()
        ]
        fired_frac = {
            name: float((valid & mask).sum() / valid.sum()) for name, mask in fired.items()
        }
        table["gate_fired_frac"] = [
            fired_frac.get(str(r.model), float("nan")) for r in table.itertuples()
        ]
        threshold_of = {f"gated_wb_{t:g}": t for t in thresholds_mm}
        table["threshold_mm"] = [
            threshold_of.get(str(r.model), float("nan")) for r in table.itertuples()
        ]
        table["model"] = table["model"].map(
            lambda name, gated=frozenset(threshold_of): "gated_wb" if name in gated else name
        )
        table["horizon_h"] = h
        tables.append(table[RESULT_COLUMNS])
    return pd.concat(tables, ignore_index=True), selected_by_horizon

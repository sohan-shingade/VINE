"""Reusable evaluation reporting (D5).

Turns aligned truth + named prediction series into the tidy tables every
track's ship decision reads (ADR-0003): a fair identical-row holdout mask so
every model is scored on exactly the same rows, deterministic fold ids built
directly on `expanding_splits` so they always match what `walk_forward`
trained/tested on, and one detailed report with aggregate metrics, per-fold
metrics, and the underlying held-out rows. No metric formula is re-derived
here — everything is assembled from `vine.d5_evaluation.metrics` and
`vine.d5_evaluation.walkforward`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TypedDict

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from vine.d5_evaluation.metrics import BinaryMetrics, binary_classification_metrics, mae, rmse
from vine.d5_evaluation.walkforward import expanding_splits, skill


def fold_assignment(n: int, n_folds: int = 5, min_train: int | None = None) -> NDArray[np.int64]:
    """Deterministic per-row fold id for `n` time-ordered rows.

    Rows before the holdout region get `-1`; holdout rows get a 0-indexed
    fold id. Built directly on `expanding_splits`, so the ids always match
    the folds `walk_forward` actually trained/tested on for the same
    `(n, n_folds, min_train)`.
    """
    ids = np.full(n, -1, dtype=np.int64)
    for i, (_, test) in enumerate(expanding_splits(n, n_folds, min_train)):
        ids[test] = i
    return ids


def fold_masks(index: pd.Index, n_folds: int = 5, min_train: int | None = None) -> list[pd.Series]:
    """One boolean mask per fold, aligned to `index`, in fold order.

    `mask[i]` selects exactly the rows `fold_assignment` labels `i`.
    """
    ids = fold_assignment(len(index), n_folds, min_train)
    return [pd.Series(ids == i, index=index, name=f"fold_{i}") for i in range(n_folds)]


def holdout_mask(
    y: pd.Series,
    preds: Mapping[str, pd.Series],
    n_folds: int = 5,
    min_train: int | None = None,
) -> pd.Series:
    """Boolean mask selecting holdout rows where truth + every prediction are present.

    This is the fairness guarantee behind every skill number in the program:
    every model in `preds` is scored on exactly these rows, never on rows
    where only the easier models happen to have a value. Rows before the
    holdout region (see `fold_assignment`) are always excluded, even if a
    prediction series has non-NaN values there.

    Args:
        y: ground-truth series.
        preds: named prediction series — each must share `y`'s index (e.g.
            the series `walk_forward` returns).
        n_folds, min_train: passed through to `fold_assignment` /
            `expanding_splits`; must match the split the predictions were
            made with.

    Returns:
        Boolean series aligned to `y.index`.

    Raises:
        ValueError: `preds` is empty, or a prediction isn't aligned to
            `y.index`.
    """
    if not preds:
        raise ValueError("preds is empty — nothing to compare against")
    valid = y.notna()
    for name, p in preds.items():
        if not p.index.equals(y.index):
            raise ValueError(f"prediction '{name}' is not aligned to y's index")
        valid &= p.notna()
    ids = fold_assignment(len(y), n_folds, min_train)
    valid &= ids >= 0
    return valid


class Report(TypedDict):
    """Full evaluation report for one truth series against named predictions."""

    aggregate: pd.DataFrame
    per_fold: pd.DataFrame
    predictions: pd.DataFrame


def build_report(
    y: pd.Series,
    preds: Mapping[str, pd.Series],
    irrigate_below: float,
    *,
    baseline: str = "persistence",
    n_folds: int = 5,
    min_train: int | None = None,
) -> Report:
    """One tidy evaluation report: aggregate + per-fold metrics, plus the raw holdout rows.

    Every model in `preds` (including `baseline`) is scored on the identical
    holdout rows (`holdout_mask`), so MAE/RMSE/skill/binary-metric comparisons
    are fair by construction. Skill is always `1 - model_mae / baseline_mae`
    (`vine.d5_evaluation.walkforward.skill`), matching the track-wide
    "vs persistence" convention (ADR-0003); per-fold skill uses that fold's
    own baseline error, so one easy/hard fold can't be hidden by the pooled
    aggregate.

    Args:
        y: ground truth, one row per time step.
        preds: named prediction series aligned to `y.index` — typically
            `walk_forward` outputs, one per model/baseline. Must include
            `baseline`.
        irrigate_below: decision threshold for the binary metrics
            (`value < irrigate_below` is the "should irrigate" event).
        baseline: key in `preds` that MAE/RMSE skill is measured against.
        n_folds, min_train: must match the split the predictions were made
            with (see `expanding_splits`).

    Returns:
        `Report` with three frames:
        - `aggregate`: indexed by model — `n`, `mae`, `rmse`,
          `skill_vs_persistence`, plus every `BinaryMetrics` field.
        - `per_fold`: one row per (model, fold) — `fold`, `n`, `mae`, `rmse`,
          `skill_vs_persistence`.
        - `predictions`: held-out rows only, columns `fold`, `y_true`, and
          one column per model in `preds`.

    Raises:
        ValueError: `baseline` isn't a key in `preds`, or no rows are
            scorable (e.g. an all-gap holdout) — see `holdout_mask`.
    """
    if baseline not in preds:
        raise ValueError(f"baseline '{baseline}' not found in preds: {list(preds)}")

    valid = holdout_mask(y, preds, n_folds, min_train)
    n = int(valid.sum())
    if n == 0:
        raise ValueError("no scorable rows (all-gap holdout?)")

    masks = fold_masks(y.index, n_folds, min_train)
    baseline_pred = preds[baseline]

    yt = y[valid].to_numpy()
    is_event = yt < irrigate_below
    baseline_mae = mae(yt, baseline_pred[valid].to_numpy())

    agg_rows = []
    fold_rows = []
    for name, p in preds.items():
        yp = p[valid].to_numpy()
        model_mae = mae(yt, yp)
        bm: BinaryMetrics = binary_classification_metrics(is_event, yp < irrigate_below)
        agg_rows.append(
            {
                "model": name,
                "n": n,
                "mae": model_mae,
                "rmse": rmse(yt, yp),
                "skill_vs_persistence": skill(model_mae, baseline_mae),
                **bm,
            }
        )

        for i, fmask in enumerate(masks):
            m = valid & fmask
            if not m.any():
                continue
            yt_f = y[m].to_numpy()
            fold_mae = mae(yt_f, p[m].to_numpy())
            fold_baseline_mae = mae(yt_f, baseline_pred[m].to_numpy())
            fold_rows.append(
                {
                    "model": name,
                    "fold": i,
                    "n": int(m.sum()),
                    "mae": fold_mae,
                    "rmse": rmse(yt_f, p[m].to_numpy()),
                    "skill_vs_persistence": skill(fold_mae, fold_baseline_mae),
                }
            )

    aggregate = pd.DataFrame(agg_rows).set_index("model")
    per_fold = pd.DataFrame(
        fold_rows, columns=["model", "fold", "n", "mae", "rmse", "skill_vs_persistence"]
    )

    ids = fold_assignment(len(y), n_folds, min_train)
    pred_cols: dict[str, pd.Series] = {
        "fold": pd.Series(ids, index=y.index)[valid],
        "y_true": y[valid],
    }
    for name, p in preds.items():
        pred_cols[name] = p[valid]
    predictions = pd.DataFrame(pred_cols)

    return {"aggregate": aggregate, "per_fold": per_fold, "predictions": predictions}

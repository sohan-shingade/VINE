"""Walk-forward validation for time-series forecasts (D5).

Time-series models must never be evaluated on a random split — training rows
from the future leak trivially (tomorrow's moisture predicts today's). Walk-
forward keeps causality: fit on everything before a fold, predict that fold,
slide forward. Pure functions; models come in as `fit_predict` callables

    fit_predict(X_train, y_train, X_test) -> array of len(X_test)

so baselines and learned models are evaluated identically (ADR-0003).
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd

FitPredict = Callable[[pd.DataFrame, pd.Series, pd.DataFrame], "np.ndarray"]


def expanding_splits(
    n: int, n_folds: int = 5, min_train: int | None = None
) -> list[tuple[slice, slice]]:
    """Expanding-window train/test splits over `n` time-ordered rows.

    The last `n - min_train` rows are cut into `n_folds` contiguous test folds;
    each fold trains on *everything before it* (the window expands). Defaults
    to holding out the second half (`min_train = n // 2`).

    Returns (train_slice, test_slice) pairs; test slices tile the holdout
    region exactly, in order, with no overlap.
    """
    if min_train is None:
        min_train = n // 2
    test_len = n - min_train
    if test_len < n_folds:
        raise ValueError(f"not enough rows to test: {test_len} holdout rows < {n_folds} folds")
    bounds = [min_train + round(i * test_len / n_folds) for i in range(n_folds + 1)]
    return [(slice(0, a), slice(a, b)) for a, b in zip(bounds, bounds[1:], strict=False)]


def walk_forward(
    X: pd.DataFrame,
    y: pd.Series,
    fit_predict: FitPredict,
    n_folds: int = 5,
    min_train: int | None = None,
) -> pd.Series:
    """Out-of-sample predictions for the holdout region, fold by fold.

    Returns a series aligned to `y.index`: NaN before the first test fold,
    the fold-wise causal predictions after. `fit_predict` only ever sees
    training rows strictly before the rows it predicts.
    """
    preds = pd.Series(np.nan, index=y.index, dtype=float)
    for tr, te in expanding_splits(len(y), n_folds, min_train):
        out = fit_predict(X.iloc[tr], y.iloc[tr], X.iloc[te])
        preds.iloc[te] = np.asarray(out, dtype=float)
    return preds


def skill(model_err: float, baseline_err: float) -> float:
    """Skill score `1 - model/baseline`: positive means the model beats the baseline.

    The shipping gate of ADR-0003 in one number. Zero baseline error (a solved
    or degenerate series) gives skill 0 — nothing to improve on.
    """
    if baseline_err == 0 or not np.isfinite(baseline_err):
        return 0.0
    return 1.0 - model_err / baseline_err

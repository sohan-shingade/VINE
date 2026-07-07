"""Tests for walk-forward validation (D5)."""

import numpy as np
import pandas as pd
import pytest

from vine.d5_evaluation.walkforward import expanding_splits, skill, walk_forward


def test_expanding_splits_tile_the_holdout_exactly():
    splits = expanding_splits(100, n_folds=4)
    # test folds cover rows 50..100 in order, no gaps or overlap
    covered = []
    for train, test in splits:
        assert train.start == 0
        assert train.stop == test.start  # train is everything before the fold
        covered.extend(range(test.start, test.stop))
    assert covered == list(range(50, 100))


def test_expanding_splits_rejects_tiny_series():
    with pytest.raises(ValueError, match="not enough rows"):
        expanding_splits(8, n_folds=5)


def test_walk_forward_is_causal():
    """fit_predict must never see training rows at or after the rows it predicts."""
    idx = pd.date_range("2026-01-01", periods=60, freq="1h", tz="UTC")
    y = pd.Series(np.arange(60, dtype=float), index=idx)
    X = pd.DataFrame({"f": np.arange(60, dtype=float)}, index=idx)

    def fit_predict(X_tr, y_tr, X_te):
        assert y_tr.index.max() < X_te.index.min()
        return np.full(len(X_te), y_tr.iloc[-1])

    preds = walk_forward(X, y, fit_predict, n_folds=3)
    assert preds.iloc[:30].isna().all()  # no predictions before the holdout
    assert preds.iloc[30:].notna().all()


def test_walk_forward_refits_per_fold():
    idx = pd.date_range("2026-01-01", periods=40, freq="1h", tz="UTC")
    y = pd.Series(np.arange(40, dtype=float), index=idx)
    X = pd.DataFrame(index=idx)
    # "last training value" grows fold over fold — proves refitting happens
    preds = walk_forward(X, y, lambda X_tr, y_tr, X_te: np.full(len(X_te), y_tr.iloc[-1]), 4)
    fold_values = preds.dropna().unique()
    assert len(fold_values) == 4
    assert (np.diff(fold_values) > 0).all()


def test_skill_sign_convention():
    assert skill(1.0, 2.0) == 0.5  # halved the baseline error -> positive
    assert skill(2.0, 1.0) == -1.0  # doubled it -> negative
    assert skill(1.0, 0.0) == 0.0  # degenerate baseline -> no skill claimable

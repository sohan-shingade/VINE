"""Tests for walk-forward validation (D5)."""

import numpy as np
import pandas as pd
import pytest

from vine.d5_evaluation.walkforward import (
    expanding_splits,
    purged_train_slice,
    skill,
    walk_forward,
)


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


def test_purged_train_slice_has_exact_horizon_boundary():
    train = slice(0, 30)

    assert purged_train_slice(train, purge=0) == slice(0, 30)
    assert purged_train_slice(train, purge=5) == slice(0, 25)
    assert purged_train_slice(slice(4, 10), purge=99) == slice(4, 4)


def test_walk_forward_uses_the_central_purged_boundary():
    n = 60
    X = pd.DataFrame({"x": np.arange(n, dtype=float)})
    y = pd.Series(np.arange(n, dtype=float))
    seen: list[tuple[list[int], int]] = []

    def fit_predict(X_train, y_train, X_test):
        seen.append((y_train.astype(int).tolist(), int(X_test.index[0])))
        return np.zeros(len(X_test))

    walk_forward(X, y, fit_predict, n_folds=3, purge=5)
    splits = expanding_splits(n, 3)
    assert seen == [(list(range(tr.start or 0, te.start - 5)), te.start) for tr, te in splits]


def test_purged_train_slice_rejects_negative_purge():
    with pytest.raises(ValueError, match="purge"):
        purged_train_slice(slice(0, 40), purge=-1)

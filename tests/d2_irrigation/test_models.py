"""Tests for D2 learned forecasters."""

import numpy as np
import pandas as pd

from vine.d2_irrigation.models import make_ridge


def _frame(n=100, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2026-01-01", periods=n, freq="1h", tz="UTC")
    X = pd.DataFrame({"a": rng.normal(size=n), "b": rng.normal(size=n)}, index=idx)
    y = pd.Series(2 * X["a"] - X["b"] + 5, index=idx)
    return X, y


def test_ridge_recovers_a_linear_relationship():
    X, y = _frame()
    preds = make_ridge(alpha=1e-3)(X.iloc[:80], y.iloc[:80], X.iloc[80:])
    assert np.abs(preds - y.iloc[80:].to_numpy()).max() < 0.1


def test_ridge_survives_all_nan_feature_columns():
    """The D1 frame carries all-NaN columns (std over a 1-sample window) — ridge
    must drop them instead of finding zero complete training rows."""
    X, y = _frame()
    X["soil_water_std_1h"] = np.nan
    preds = make_ridge()(X.iloc[:80], y.iloc[:80], X.iloc[80:])
    assert np.isfinite(preds).all()


def test_ridge_leaves_nan_where_test_features_missing():
    X, y = _frame()
    X.iloc[90, 0] = np.nan
    preds = make_ridge()(X.iloc[:80], y.iloc[:80], X.iloc[80:])
    assert np.isnan(preds[10])  # row 90 overall
    assert np.isfinite(np.delete(preds, 10)).all()

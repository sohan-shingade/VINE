"""Tests for D2 learned forecasters."""

import numpy as np
import pandas as pd

from vine.d2_irrigation.models import make_arima, make_ridge


def _frame(n=100, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2026-01-01", periods=n, freq="1h", tz="UTC")
    X = pd.DataFrame({"a": rng.normal(size=n), "b": rng.normal(size=n)}, index=idx)
    y = pd.Series(2 * X["a"] - X["b"] + 5, index=idx)
    return X, y


def _ar2_series(n=300, seed=1):
    """A strongly autocorrelated, stationary AR(2) series — low noise so a model
    that captures the dynamics should clearly beat "predict the last value"."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2026-01-01", periods=n, freq="1h", tz="UTC")
    y = np.zeros(n)
    y[0], y[1] = 10.0, 10.0
    for t in range(2, n):
        y[t] = 0.6 * y[t - 1] + 0.3 * y[t - 2] + rng.normal(scale=0.05)
    return pd.Series(y, index=idx)


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


def test_arima_beats_persistence_on_ar2():
    """Built the way the harness would: X_test[target_col] = y.shift(h) sliced
    to the fold, so it holds the true decision-time observation for each row."""
    y = _ar2_series()
    h = 1
    X = pd.DataFrame({"soil_water": y.shift(h)}, index=y.index)
    n_train = 200
    X_train, y_train = X.iloc[:n_train], y.iloc[:n_train]
    X_test, y_test = X.iloc[n_train:], y.iloc[n_train:]

    preds = make_arima(order=(2, 0, 0), horizon=h)(X_train, y_train, X_test)
    persistence = X_test["soil_water"].to_numpy()  # = last observed value

    arima_mae = np.nanmean(np.abs(preds - y_test.to_numpy()))
    persistence_mae = np.nanmean(np.abs(persistence - y_test.to_numpy()))
    assert arima_mae < persistence_mae


def test_arima_handles_nan_gaps_in_training():
    """A sensor gap in y_train must not raise (SARIMAX handles missing endog
    via the Kalman filter) and must not poison predictions for rows whose
    decision-time observation is actually present."""
    y = _ar2_series(n=300, seed=2)
    h = 1
    y_gappy = y.copy()
    y_gappy.iloc[50:60] = np.nan  # a 10-hour sensor gap
    X = pd.DataFrame({"soil_water": y_gappy.shift(h)}, index=y.index)
    n_train = 200
    X_train, y_train = X.iloc[:n_train], y_gappy.iloc[:n_train]
    X_test = X.iloc[n_train:]

    preds = make_arima(order=(2, 0, 0), horizon=h)(X_train, y_train, X_test)
    assert len(preds) == len(X_test)
    known = X_test["soil_water"].notna().to_numpy()
    assert np.isfinite(preds[known]).all()


def test_arima_early_fold_rows_cannot_see_past_their_anchor():
    """The first h-1 rows of a fold have decision times *inside* the training
    window. With order (0,1,0) the forecast is exactly the last observation the
    filter has seen, so poisoning the training tail (positions past row 0's
    anchor) exposes any state leak: the eval-reviewer found the original
    implementation forecast those rows from the full fitted state."""
    h = 6
    rng = np.random.default_rng(4)
    idx = pd.date_range("2026-01-01", periods=160, freq="1h", tz="UTC")
    y = pd.Series(np.cumsum(rng.normal(0, 0.1, size=160)), index=idx)
    y.iloc[95:100] = 1000.0  # poison the last h-1 training positions

    X = pd.DataFrame({"soil_water": y.shift(h)}, index=y.index)
    n_train = 100
    preds = make_arima(order=(0, 1, 0), horizon=h)(
        X.iloc[:n_train], y.iloc[:n_train], X.iloc[n_train:]
    )
    # Row 0's anchor is position n_train - h = 94, before the poison: a causal
    # random-walk forecast is ~y[94] (tiny), a leaky one is ~1000.
    assert np.isfinite(preds[0])
    assert abs(preds[0] - y.iloc[94]) < 10.0
    # Row h-1 legitimately sees the whole training window, poison included.
    assert preds[h - 1] > 500.0


def test_arima_output_length_matches_test_even_when_unfittable():
    """Output length must equal len(X_test) always, even when there isn't
    enough training data to fit honestly (must return NaN, not raise)."""
    y = _ar2_series(n=50, seed=3)
    h = 6
    X = pd.DataFrame({"soil_water": y.shift(h)}, index=y.index)
    X_test = X.iloc[10:]
    preds = make_arima(order=(2, 1, 2), horizon=h)(X.iloc[:10], y.iloc[:10], X_test)
    assert len(preds) == len(X_test)
    assert np.isnan(preds).all()  # 10 rows < the 20-row minimum to fit

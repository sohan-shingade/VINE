"""Tests for D2 learned forecasters."""

import numpy as np
import pandas as pd

from vine.d2_irrigation.models import (
    make_arima,
    make_lstm,
    make_prophet,
    make_ridge,
    make_water_balance,
)
from vine.d5_evaluation.walkforward import walk_forward


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


def test_gbt_learns_a_nonlinear_relationship_ridge_cannot():
    from vine.d2_irrigation.models import make_gbt, make_ridge

    rng = np.random.default_rng(0)
    idx = pd.date_range("2026-01-01", periods=400, freq="1h", tz="UTC")
    X = pd.DataFrame({"a": rng.normal(size=400), "b": rng.normal(size=400)}, index=idx)
    y = pd.Series(X["a"] * X["b"], index=idx)  # pure interaction: linear R^2 ~ 0
    gbt = make_gbt(max_iter=200)(X.iloc[:300], y.iloc[:300], X.iloc[300:])
    ridge = make_ridge()(X.iloc[:300], y.iloc[:300], X.iloc[300:])
    truth = y.iloc[300:].to_numpy()
    assert np.abs(gbt - truth).mean() < np.abs(ridge - truth).mean()


def test_gbt_predicts_through_nan_features():
    from vine.d2_irrigation.models import make_gbt

    X, y = _frame()
    X.iloc[90, 0] = np.nan  # unlike ridge/forest, gbt handles missing natively
    X["soil_water_std_1h"] = np.nan  # ...but all-NaN columns crash its binner
    preds = make_gbt()(X.iloc[:80], y.iloc[:80], X.iloc[80:])
    assert np.isfinite(preds).all()


def test_forest_matches_ridge_nan_policy():
    from vine.d2_irrigation.models import make_forest

    X, y = _frame()
    X.iloc[90, 0] = np.nan
    preds = make_forest(n_estimators=20)(X.iloc[:80], y.iloc[:80], X.iloc[80:])
    assert np.isnan(preds[10])
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


def _walk_forward_arima(y: pd.Series, horizon: int, min_train: int) -> pd.Series:
    X = pd.DataFrame({"soil_water": y.shift(horizon)}, index=y.index)
    return walk_forward(
        X,
        y,
        make_arima(order=(0, 1, 0), horizon=horizon),
        n_folds=1,
        min_train=min_train,
        purge=horizon - 1,
    )


def test_arima_walk_forward_purge_preserves_first_test_anchor():
    """Physical label purging must not shift ARIMA's original fold coordinates."""
    h = 6
    min_train = 80
    rng = np.random.default_rng(14)
    idx = pd.date_range("2026-01-01", periods=160, freq="1h", tz="UTC")
    y = pd.Series(np.cumsum(rng.normal(0, 0.1, size=len(idx))), index=idx)

    preds = _walk_forward_arima(y, h, min_train)

    assert np.isfinite(preds.iloc[min_train])
    assert abs(preds.iloc[min_train] - y.iloc[min_train - h]) < 1e-6


def test_arima_walk_forward_purge_blocks_post_decision_poison():
    """The first forecast must be invariant to every value after its anchor."""
    h = 6
    min_train = 80
    rng = np.random.default_rng(14)
    idx = pd.date_range("2026-01-01", periods=160, freq="1h", tz="UTC")
    clean = pd.Series(np.cumsum(rng.normal(0, 0.1, size=len(idx))), index=idx)
    poisoned = clean.copy()
    poisoned.iloc[min_train - h + 1 :] += 1000.0

    expected = _walk_forward_arima(clean, h, min_train)
    actual = _walk_forward_arima(poisoned, h, min_train)

    assert np.isfinite(expected.iloc[min_train])
    assert actual.iloc[min_train] == expected.iloc[min_train]


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


def _wb_frame(n: int, h: int, seed: int) -> tuple[pd.DataFrame, pd.Series]:
    """Synthetic: moisture that dries with ET0 and jumps on rain, + lead-time cols."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2026-01-01", periods=n, freq="1h", tz="UTC")
    et0_next = np.abs(rng.normal(3, 1, n))  # cumulative ET0 over the window
    precip_next = np.where(rng.random(n) < 0.15, rng.exponential(4, n), 0.0)  # sparse rain
    # true change: down with ET0, up with rain
    delta = -0.4 * et0_next + 0.5 * precip_next + rng.normal(0, 0.2, n)
    level = 27 + np.cumsum(rng.normal(0, 0.05, n))
    y = pd.Series(level, index=idx)
    X = pd.DataFrame(
        {
            "soil_water": y.shift(h),  # persistence anchor at decision time
            f"et0_next_{h}h": pd.Series(et0_next, index=idx).shift(h),
            f"precip_next_{h}h": pd.Series(precip_next, index=idx).shift(h),
        },
        index=idx,
    )
    # bake the modeled change into y so the regression is learnable
    y = X["soil_water"] + pd.Series(delta, index=idx).shift(0)
    return X, y


def test_water_balance_predicts_and_needs_drivers():
    h = 24
    X, y = _wb_frame(400, h, seed=1)
    preds = make_water_balance("soil_water", horizon=h)(X.iloc[:300], y.iloc[:300], X.iloc[300:])
    assert len(preds) == len(X.iloc[300:])
    assert np.isfinite(preds).any()
    # Without the lead-time columns it cannot do a water balance -> all NaN.
    bare = X[["soil_water"]]
    none = make_water_balance("soil_water", horizon=h)(
        bare.iloc[:300], y.iloc[:300], bare.iloc[300:]
    )
    assert np.isnan(none).all()


def test_water_balance_gate_falls_back_to_persistence_on_dry_rows():
    """Gated: rows with forecast rain <= threshold must equal exact persistence."""
    h = 24
    X, y = _wb_frame(400, h, seed=2)
    gated = make_water_balance("soil_water", horizon=h, gate_precip_mm=0.3)
    preds = gated(X.iloc[:300], y.iloc[:300], X.iloc[300:])
    Xte = X.iloc[300:]
    dry = Xte[f"precip_next_{h}h"].to_numpy() <= 0.3
    persistence = Xte["soil_water"].to_numpy()
    # On dry rows the prediction is exactly the persistence anchor (no correction).
    finite_dry = dry & np.isfinite(preds)
    assert finite_dry.any()
    assert np.allclose(preds[finite_dry], persistence[finite_dry])
    # On rainy rows it must differ from persistence (correction applied).
    wet = (~dry) & np.isfinite(preds)
    if wet.any():
        assert not np.allclose(preds[wet], persistence[wet])


def test_water_balance_robust_resists_a_storm_outlier():
    """Huber Δ-regression must not let one extreme rain row dominate the fit.

    Inject a single absurd storm into training: OLS chases it and mis-predicts a
    normal test row; the robust fit down-weights it and stays close to truth."""
    h = 24
    X, y = _wb_frame(400, h, seed=7)
    Xtr, ytr = X.iloc[:300].copy(), y.iloc[:300].copy()
    Xtr.iloc[150, Xtr.columns.get_loc(f"precip_next_{h}h")] = 500.0  # one impossible storm
    ols = make_water_balance("soil_water", horizon=h)(Xtr, ytr, X.iloc[300:])
    rob = make_water_balance("soil_water", horizon=h, robust=True)(Xtr, ytr, X.iloc[300:])
    truth = y.iloc[300:].to_numpy()
    both = np.isfinite(ols) & np.isfinite(rob) & np.isfinite(truth)
    assert np.abs(rob[both] - truth[both]).mean() <= np.abs(ols[both] - truth[both]).mean()


def test_water_balance_adaptive_blend_falls_back_to_persistence_when_useless():
    """If the drivers carry no real signal, adaptive λ must collapse to 0 so the
    model returns exact persistence — never worse than the baseline it wraps."""
    h = 24
    rng = np.random.default_rng(11)
    n = 400
    idx = pd.date_range("2026-01-01", periods=n, freq="1h", tz="UTC")
    # Random walk with NO relationship to the (random) weather drivers.
    y = pd.Series(27 + np.cumsum(rng.normal(0, 0.1, n)), index=idx)
    X = pd.DataFrame(
        {
            "soil_water": y.shift(h),
            f"et0_next_{h}h": rng.normal(3, 1, n),  # pure noise vs the target
            f"precip_next_{h}h": np.where(rng.random(n) < 0.2, rng.exponential(3, n), 0.0),
        },
        index=idx,
    )
    adaptive = make_water_balance("soil_water", horizon=h, gate_precip_mm=0.3, adaptive_blend=True)
    always = make_water_balance("soil_water", horizon=h, gate_precip_mm=0.3)  # λ=1 always
    preds = adaptive(X.iloc[:300], y.iloc[:300], X.iloc[300:])
    always_preds = always(X.iloc[:300], y.iloc[:300], X.iloc[300:])
    truth = y.iloc[300:].to_numpy()
    persistence = X.iloc[300:]["soil_water"].to_numpy()
    finite = np.isfinite(preds)
    # Most rows collapse to exact persistence (λ=0), and the blend is never
    # materially worse than persistence and beats blindly always-correcting.
    assert np.mean(np.isclose(preds[finite], persistence[finite])) > 0.5
    adaptive_mae = np.abs(preds[finite] - truth[finite]).mean()
    persistence_mae = np.abs(persistence[finite] - truth[finite]).mean()
    always_mae = np.abs(always_preds[finite] - truth[finite]).mean()
    assert adaptive_mae <= persistence_mae * 1.02
    assert adaptive_mae <= always_mae


def test_water_balance_requires_both_matching_drivers():
    h = 24
    X, y = _wb_frame(400, h, seed=4)
    model = make_water_balance("soil_water", horizon=h)
    for missing in (f"et0_next_{h}h", f"precip_next_{h}h"):
        incomplete = X.drop(columns=missing)
        preds = model(incomplete.iloc[:300], y.iloc[:300], incomplete.iloc[300:])
        assert np.isnan(preds).all()


def test_water_balance_ignores_future_test_targets():
    h = 24
    X, y = _wb_frame(400, h, seed=5)
    model = make_water_balance("soil_water", horizon=h, adaptive_blend=True)
    expected = model(X.iloc[:300], y.iloc[:300], X.iloc[300:])
    poisoned = y.copy()
    poisoned.iloc[300:] += 1e6
    actual = model(X.iloc[:300], poisoned.iloc[:300], X.iloc[300:])
    np.testing.assert_allclose(actual, expected, equal_nan=True)


def _daily_series(n=240, seed=6):
    """Soil-moisture-like series with a clear daily cycle plus slow drift."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2026-01-01", periods=n, freq="1h", tz="UTC")
    hours = np.arange(n)
    y = 30.0 + 3.0 * np.sin(2 * np.pi * hours / 24) - 0.005 * hours + rng.normal(0, 0.1, n)
    return pd.Series(y, index=idx)


def test_prophet_smoke_predicts_and_masks_missing_regressor():
    """Prophet fits on the training series with a lagged regressor and predicts
    every test row whose regressor is present; a NaN regressor row stays NaN."""
    y = _daily_series()
    h = 6
    temp = pd.Series(20 + 2 * np.sin(2 * np.pi * np.arange(len(y)) / 24), index=y.index)
    X = pd.DataFrame({"soil_water": y.shift(h), "soil_temperature": temp.shift(h)}, index=y.index)
    X.iloc[210, X.columns.get_loc("soil_temperature")] = np.nan
    preds = make_prophet(horizon=h, regressors=("soil_temperature",))(
        X.iloc[:200], y.iloc[:200], X.iloc[200:]
    )
    assert len(preds) == 40
    assert np.isnan(preds[10])  # row 210 overall: missing regressor, never imputed
    assert np.isfinite(np.delete(preds, 10)).all()


def test_prophet_returns_nan_when_training_too_short():
    y = _daily_series(n=60)
    h = 6
    X = pd.DataFrame({"soil_water": y.shift(h)}, index=y.index)
    preds = make_prophet(horizon=h)(X.iloc[:15], y.iloc[:15], X.iloc[15:])
    assert len(preds) == 45
    assert np.isnan(preds).all()  # 15 rows < the 20-row minimum to fit


def test_prophet_walk_forward_purge_blocks_post_decision_poison():
    """The first fold forecast must be invariant to values after its anchor
    (same poison-tail pattern as the ARIMA causality test)."""
    h = 6
    min_train = 80

    def run(series: pd.Series) -> pd.Series:
        X = pd.DataFrame({"soil_water": series.shift(h)}, index=series.index)
        return walk_forward(
            X,
            series,
            make_prophet(horizon=h, regressors=("soil_water",)),
            n_folds=1,
            min_train=min_train,
            purge=h - 1,
        )

    clean = _daily_series(n=160, seed=7)
    poisoned = clean.copy()
    poisoned.iloc[min_train - h + 1 :] += 1000.0

    expected = run(clean)
    actual = run(poisoned)
    assert np.isfinite(expected.iloc[min_train])
    # A leak would drag the forecast toward the +1000 poison plateau.
    assert abs(actual.iloc[min_train] - expected.iloc[min_train]) < 1.0


def _lstm_tiny(h: int, **kw):
    defaults = dict(horizon=h, features=("soil_water",), window=8, hidden=8, layers=1, epochs=2)
    defaults.update(kw)
    return make_lstm(**defaults)


def test_lstm_smoke_predicts_complete_windows_only():
    """Rows whose input window is complete get a finite forecast; a window that
    contains a sensor gap returns NaN (gaps are never imputed)."""
    y = _daily_series(n=180, seed=8)
    h = 3
    X = pd.DataFrame({"soil_water": y.shift(h)}, index=y.index)
    X.iloc[150, 0] = np.nan  # one missing decision-time observation
    preds = _lstm_tiny(h)(X.iloc[:140], y.iloc[:140], X.iloc[140:])
    assert len(preds) == 40
    # Windows ending on rows 150..157 all contain the NaN at row 150.
    assert np.isnan(preds[10:18]).all()
    assert np.isfinite(np.delete(preds, np.arange(10, 18))).all()
    finite = preds[np.isfinite(preds)]
    assert np.abs(finite - y.iloc[140:][np.isfinite(preds)].to_numpy()).mean() < 5.0


def test_lstm_returns_nan_when_training_too_short():
    y = _daily_series(n=60, seed=9)
    h = 3
    X = pd.DataFrame({"soil_water": y.shift(h)}, index=y.index)
    preds = _lstm_tiny(h)(X.iloc[:20], y.iloc[:20], X.iloc[20:])
    assert len(preds) == 40
    assert np.isnan(preds).all()  # fewer complete windows than min_samples


def test_lstm_ignores_values_past_the_first_test_anchor():
    """Poison-tail causality: training labels and inputs after row 0's decision
    time must not change row 0's forecast. Training is truncated to the labels
    row 0 may see, and its window ends at its own decision-time observation, so
    the two runs must match exactly (seeded, deterministic on CPU)."""
    h = 6
    n_train = 100
    clean = _daily_series(n=160, seed=10)
    poisoned = clean.copy()
    poisoned.iloc[n_train - h + 1 :] += 1000.0  # everything past row 0's anchor

    def run(series: pd.Series) -> np.ndarray:
        X = pd.DataFrame({"soil_water": series.shift(h)}, index=series.index)
        return _lstm_tiny(h)(X.iloc[:n_train], series.iloc[:n_train], X.iloc[n_train:])

    expected = run(clean)
    actual = run(poisoned)
    assert np.isfinite(expected[0])
    assert abs(actual[0] - expected[0]) < 1e-6


def test_lstm_walk_forward_gap_rows_are_nan_then_finite():
    """Under walk_forward with purge=h-1 the h-1 purged rows are physically
    missing, so the first window-1 test rows of the fold cannot form a complete
    window and must be NaN; later rows must be finite."""
    h = 6
    min_train = 80
    window = 8
    y = _daily_series(n=160, seed=11)
    X = pd.DataFrame({"soil_water": y.shift(h)}, index=y.index)
    preds = walk_forward(
        X,
        y,
        _lstm_tiny(h, window=window),
        n_folds=1,
        min_train=min_train,
        purge=h - 1,
    )
    fold = preds.iloc[min_train:]
    assert fold.iloc[: window - 1].isna().all()
    assert fold.iloc[window - 1 :].notna().all()

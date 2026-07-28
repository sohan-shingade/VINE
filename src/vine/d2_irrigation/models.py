"""Learned forecasters for soil moisture (D2), as `fit_predict` callables.

Ridge regression on the D1 feature frame (lags, rolling stats, weather) was
the first rung above the baselines (ADR-0003) but failed to beat persistence
on real data (negative skill everywhere — see `docs/STATE.md` 2026-07-08).
`make_arima` is the next rung: a classical SARIMAX forecaster that models the
target's own dynamics directly rather than regressing on engineered features.
Ships only if it beats persistence and seasonal-naive under walk-forward
evaluation — run `vine train irrigation <config>` for the evidence.
"""

from __future__ import annotations

import contextlib

import numpy as np
import pandas as pd

from vine.d5_evaluation.walkforward import ORIGINAL_TRAIN_STOP_ATTR, FitPredict


def make_ridge(alpha: float = 1.0) -> FitPredict:
    """Ridge regression fit_predict with the given L2 strength.

    Trains on complete rows only and predicts complete test rows; rows with a
    missing feature get NaN (gaps are flagged upstream, never imputed — the
    evaluation masks them out for every model equally).
    """

    def fit_predict(X_train: pd.DataFrame, y_train: pd.Series, X_test: pd.DataFrame) -> np.ndarray:
        from sklearn.linear_model import Ridge
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler

        # Drop features with no training signal (e.g. std over a 1-sample window
        # is all-NaN on an hourly grid) — else no row is ever "complete".
        cols = X_train.columns[X_train.notna().any()]
        ok = X_train[cols].notna().all(axis=1) & y_train.notna()
        model = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
        model.fit(X_train.loc[ok, cols], y_train[ok])

        out = np.full(len(X_test), np.nan)
        te = X_test[cols].notna().all(axis=1).to_numpy()
        if te.any():
            out[te] = model.predict(X_test.loc[te, cols])
        return out

    return fit_predict


def make_forest(n_estimators: int = 300, max_depth: int | None = None) -> FitPredict:
    """Random-forest fit_predict (sklearn), same complete-rows policy as ridge.

    Trees cannot extrapolate past their training range, so on a seasonally
    drifting *level* series a forest degrades to clipping — pair it with
    `predict_delta`, where the target is roughly stationary. random_state is
    fixed: the run is already config+seed reproducible and sklearn needs an
    explicit value.
    """

    def fit_predict(X_train: pd.DataFrame, y_train: pd.Series, X_test: pd.DataFrame) -> np.ndarray:
        from sklearn.ensemble import RandomForestRegressor

        cols = X_train.columns[X_train.notna().any()]
        ok = X_train[cols].notna().all(axis=1) & y_train.notna()
        model = RandomForestRegressor(
            n_estimators=n_estimators, max_depth=max_depth, random_state=0, n_jobs=-1
        )
        model.fit(X_train.loc[ok, cols], y_train[ok])

        out = np.full(len(X_test), np.nan)
        te = X_test[cols].notna().all(axis=1).to_numpy()
        if te.any():
            out[te] = model.predict(X_test.loc[te, cols])
        return out

    return fit_predict


def make_gbt(learning_rate: float = 0.06, max_iter: int = 300) -> FitPredict:
    """Gradient-boosted trees fit_predict — sklearn's HistGradientBoosting.

    Same model family as CatBoost/LightGBM without a new dependency, and it
    handles NaN features natively (missing values route down a learned branch),
    which suits gappy sensor frames: only rows with a missing *target* are
    dropped from training, and every test row gets a prediction. The same
    extrapolation caveat as `make_forest` applies — prefer `predict_delta`.
    """

    def fit_predict(X_train: pd.DataFrame, y_train: pd.Series, X_test: pd.DataFrame) -> np.ndarray:
        from sklearn.ensemble import HistGradientBoostingRegressor

        # Partial NaN is fine natively, but the binner crashes on a column with
        # zero finite values (e.g. std over a 1-sample window) — drop those.
        cols = X_train.columns[X_train.notna().any()]
        ok = y_train.notna()
        model = HistGradientBoostingRegressor(
            learning_rate=learning_rate, max_iter=max_iter, random_state=0
        )
        model.fit(X_train.loc[ok, cols], y_train[ok])
        return np.asarray(model.predict(X_test[cols]), dtype=float)

    return fit_predict


def make_water_balance(
    target_col: str = "soil_water",
    horizon: int = 24,
    use_level: bool = False,
    gate_precip_mm: float | None = None,
    robust: bool = False,
    saturate_k: float | None = None,
    adaptive_blend: bool = False,
    val_frac: float = 0.25,
    blend_weights: tuple[float, ...] = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0),
    min_fit_rows: int = 20,
    min_val_rows: int = 10,
    huber_max_iter: int = 500,
) -> FitPredict:
    """Persistence + a weather correction — a tiny physical water-balance model.

    Persistence misses exactly the *deterministic* part of soil-moisture change:
    water leaves by evapotranspiration (∝ ET₀) and arrives as rain. So instead
    of a big feature regression (which overfit — see ridge+forecast's single-rain
    -fold artifact), fit the change persistence misses on just the two physical
    drivers accumulated over the forecast window:

        Δ(t) = y(t) - y(t-h) ≈ β_et0 · et0_next_{h}h + β_precip · precip_next_{h}h + c

    then predict `y(t-h) + Δ̂`. Two or three coefficients, so it cannot memorize a
    fold; it can only learn "moisture falls with ET₀, rises with rain," which is
    real physics and shared across nearby probes (pools well). Needs the
    lead-time columns (`forecast_features: true`), and the experiment's horizon
    guard keeps only the matching `_next_{h}h` pair, so the window is exactly
    `(t-h, t]`. `use_level` adds the current moisture as a third feature (wetter
    soil drains faster); off by default to keep it maximally constrained.

    `gate_precip_mm` makes it a *gated* correction: persistence is near-optimal on
    quiet windows, so a correction applied to every row just adds noise there
    (helps RMSE, not MAE). With a gate, rows whose forecast rain over the window
    is ≤ the threshold fall back to exact persistence, and the physical
    correction is applied only to the active (rainy) windows where persistence
    actually misses. The model is still fit on all rows — only *application* is
    gated — so the coefficients stay well-estimated.

    `adaptive_blend` reduces downside when recent training evidence does not
    support the correction. It cannot guarantee future-fold performance. Instead
    of always applying the full correction, shrink it by a blend weight λ ∈ [0, 1]
    chosen with NO sight of the test fold:
    hold out the most recent `val_frac` of the *training* window, fit on the rest,
    and pick the λ that minimises MAE of `anchor + λ·correction` on that internal
    holdout — but only accept λ > 0 if it strictly beats λ = 0 (pure persistence)
    there. If the correction was not helping in the recent past, λ → 0 and
    the model becomes persistence on that fold. The recent holdout is an honest,
    leakage-free reliability estimate, but the next fold can still differ.

    Returns NaN where the drivers or the persistence anchor are missing (gaps are
    never imputed) — scored on the same masked rows as every other model.
    """

    def _fit(X: pd.DataFrame, d: pd.Series, feats: list[str]):
        from sklearn.linear_model import LinearRegression

        if robust:
            from sklearn.linear_model import HuberRegressor

            try:
                return HuberRegressor(max_iter=huber_max_iter).fit(X[feats], d)
            except (ValueError, FloatingPointError):
                return LinearRegression().fit(X[feats], d)
        return LinearRegression().fit(X[feats], d)

    def _correction(
        model, X: pd.DataFrame, feats: list[str], precip: str, cap: float
    ) -> np.ndarray:
        c = model.predict(X[feats])
        if gate_precip_mm is not None and precip in X.columns:
            c = np.where(X[precip].to_numpy() > gate_precip_mm, c, 0.0)
        if saturate_k is not None:
            c = np.clip(c, -cap, cap)
        return np.asarray(c, dtype=float)

    def fit_predict(X_train: pd.DataFrame, y_train: pd.Series, X_test: pd.DataFrame) -> np.ndarray:
        et0, precip = f"et0_next_{horizon}h", f"precip_next_{horizon}h"
        drivers = [et0, precip]
        out = np.full(len(X_test), np.nan)
        required = [target_col, *drivers]
        if any(c not in X_train.columns or c not in X_test.columns for c in required):
            return out  # both drivers + persistence anchor are required
        feats = drivers + ([target_col] if use_level else [])

        anchor_tr = X_train[target_col]  # last obs known at decision time = persistence
        delta_tr = y_train - anchor_tr  # the change persistence misses
        ok = (X_train[feats].notna().all(axis=1) & delta_tr.notna()).to_numpy()
        if int(ok.sum()) < min_fit_rows:
            return out
        Xtr_ok, dtr_ok = X_train.loc[ok, feats], delta_tr[ok]
        cap = saturate_k * float(np.abs(dtr_ok).max()) if saturate_k is not None else 0.0

        lam = 1.0
        if adaptive_blend:
            # Pick λ on the most-recent slice of training only (never the test
            # fold). Fit on the earlier part, score anchor + λ·correction on the
            # holdout, accept λ>0 only if it strictly beats persistence there.
            n_ok = int(ok.sum())
            cut = int(n_ok * (1.0 - val_frac))
            if cut >= min_fit_rows and n_ok - cut >= min_val_rows:
                Xin, din = Xtr_ok.iloc[:cut], dtr_ok.iloc[:cut]
                Xvl, dvl = Xtr_ok.iloc[cut:], dtr_ok.iloc[cut:]
                val_cap = saturate_k * float(np.abs(din).max()) if saturate_k is not None else 0.0
                m_in = _fit(Xin, din, feats)
                corr_vl = _correction(m_in, Xvl, feats, precip, val_cap)
                truth_delta = dvl.to_numpy()  # y - anchor on the holdout
                errs = {
                    round(g, 2): float(np.mean(np.abs(truth_delta - g * corr_vl)))
                    for g in blend_weights
                }
                best = min(errs, key=lambda g: errs[g])
                lam = best if errs[best] < errs[0.0] else 0.0  # strict beat, else persistence

        model = _fit(Xtr_ok, dtr_ok, feats)
        te = X_test[feats].notna().all(axis=1).to_numpy()
        anchor_te = X_test[target_col].to_numpy()
        if te.any() and lam > 0:
            out[te] = anchor_te[te] + lam * _correction(model, X_test.loc[te], feats, precip, cap)
        elif te.any():
            out[te] = anchor_te[te]  # λ=0 -> exact persistence
        return out

    return fit_predict


def make_arima(
    order: tuple[int, int, int] = (2, 1, 2),
    horizon: int = 1,
    target_col: str = "soil_water",
) -> FitPredict:
    """SARIMAX fit_predict producing genuine `horizon`-step-ahead forecasts.

    Fits once on `y_train`, then rolls the fitted Kalman filter forward one
    observation at a time and reads off the `horizon`-step-ahead forecast at
    each point — `res.extend()` only reruns the filter (cheap), it never
    re-optimizes, so a fold costs one `fit()` plus O(len(X_test)) filter
    updates, not a refit per row.

    Causality argument: prediction row `i` (target time `fold_start + i`) may
    only use observations up to `fold_start + i - horizon`. `X_test[target_col]`
    is that exact observation for every row (it's `target.shift(horizon)`,
    same as every other feature the experiment builds), so feeding it into the
    filter one row at a time, in order, reconstructs precisely the history row
    `i` is allowed to see — never more. Walk-forward records the original fold
    start on the physically purged training frame, so these coordinates do not
    shift when `purge=horizon-1`. If called without a purge, the first
    `horizon - 1` anchors lie inside training and the filter is re-run on each
    allowed prefix (`res.apply`), rather than leaking the fitted tail. NaN gaps
    are passed straight into the Kalman filter (SARIMAX handles missing endog
    natively, no imputation); rows that can't be honestly forecast (too little
    training data, or an unreachable decision-time observation) come back NaN.
    """

    def fit_predict(X_train: pd.DataFrame, y_train: pd.Series, X_test: pd.DataFrame) -> np.ndarray:
        from statsmodels.tsa.statespace.sarimax import SARIMAX

        n_train, n_test = len(y_train), len(X_test)
        fold_start = X_train.attrs.get(ORIGINAL_TRAIN_STOP_ATTR, n_train)
        if not isinstance(fold_start, int) or fold_start < n_train:
            fold_start = n_train
        out = np.full(n_test, np.nan)
        if y_train.notna().sum() < 20:
            return out  # too little signal to fit honestly

        # y observed at decision time (t - horizon) for every test row, recovered
        # honestly from the shifted feature frame — see docstring.
        recovered = (
            X_test[target_col].to_numpy()
            if target_col in X_test.columns
            else np.full(n_test, np.nan)
        )

        try:
            res = SARIMAX(
                y_train.to_numpy(),
                order=order,
                enforce_stationarity=False,
                enforce_invertibility=False,
            ).fit(disp=False)
        except Exception:
            return out  # non-convergent fit — nothing honest to predict

        seen = n_train - 1  # last original position folded into the fitted state
        for i in range(n_test):
            anchor = fold_start + i - horizon  # last position row i may observe
            if anchor < 0:
                continue
            if anchor < seen:
                # Unpurged early rows: the fitted state contains observations past
                # the anchor, and extend() cannot rewind. Re-filter only the causal
                # prefix with the already fitted parameters.
                trunc = y_train.to_numpy()[: anchor + 1]
                if np.isfinite(trunc).sum() < 20:
                    continue
                with contextlib.suppress(Exception):  # unfilterable prefix -> NaN
                    out[i] = res.apply(trunc).forecast(horizon)[-1]
                continue
            if anchor > seen:
                # Each recovered value corresponds to its test row's exact
                # decision-time observation. Start where the fitted state ends,
                # using original fold coordinates even when training was purged.
                first = seen - fold_start + horizon + 1
                new_vals = recovered[first : i + 1]
                if len(new_vals) == 0:
                    continue
                res = res.extend(new_vals)
                seen = anchor
            out[i] = res.forecast(horizon)[-1]
        return out

    return fit_predict

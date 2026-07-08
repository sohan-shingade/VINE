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

from vine.d5_evaluation.walkforward import FitPredict


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

    Causality argument: prediction row `i` (target time `train_end + i`) may
    only use observations up to `train_end + i - horizon`. `X_test[target_col]`
    is that exact observation for every row (it's `target.shift(horizon)`,
    same as every other feature the experiment builds), so feeding it into the
    filter one row at a time, in order, reconstructs precisely the history row
    `i` is allowed to see — never more. For the first `horizon - 1` rows of a
    fold that anchor lies *inside* the training window, so the filter is re-run
    on the truncated history (`res.apply`) — the fitted state itself would leak
    observations past the anchor. Parameters are still estimated once on the
    full training fold: that's the standard walk-forward boundary, the same one
    every other model gets (features/targets up to the fold start). NaN gaps
    are passed straight into the Kalman filter (SARIMAX handles missing endog
    natively, no imputation); rows that can't be honestly forecast (too little
    training data, or an unreachable decision-time observation) come back NaN.
    """

    def fit_predict(X_train: pd.DataFrame, y_train: pd.Series, X_test: pd.DataFrame) -> np.ndarray:
        from statsmodels.tsa.statespace.sarimax import SARIMAX

        n_train, n_test = len(y_train), len(X_test)
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

        seen = n_train - 1  # last global position folded into res's filtered state
        for i in range(n_test):
            anchor = n_train + i - horizon  # last position row i is allowed to see
            if anchor < 0:
                continue
            if anchor < seen:
                # Early fold rows: the fitted state already contains train
                # observations past the anchor, and extend() can't rewind — so
                # re-run the filter (params unchanged) on the allowed prefix.
                trunc = y_train.to_numpy()[: anchor + 1]
                if np.isfinite(trunc).sum() < 20:
                    continue
                with contextlib.suppress(Exception):  # unfilterable prefix -> NaN
                    out[i] = res.apply(trunc).forecast(horizon)[-1]
                continue
            if anchor > seen:
                new_vals = recovered[seen - n_train + horizon + 1 : i + 1]
                if len(new_vals) == 0:
                    continue
                res = res.extend(new_vals)
                seen = anchor
            out[i] = res.forecast(horizon)[-1]
        return out

    return fit_predict

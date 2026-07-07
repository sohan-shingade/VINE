"""Learned forecasters for soil moisture (D2), as `fit_predict` callables.

First rung above the baselines (ADR-0003): standardized ridge regression on
the D1 feature frame (lags, rolling stats, weather). Ships only if it beats
persistence and seasonal-naive under walk-forward evaluation — run
`vine train irrigation configs/d2_irrigation/ridge.yaml` for the evidence.
"""

from __future__ import annotations

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

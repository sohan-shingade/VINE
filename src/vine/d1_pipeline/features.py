"""Time-series feature engineering shared by the irrigation & harvest tracks.

Turns regularized sensor frames into model-ready features: rolling statistics,
lag features, and cumulative growing degree-days (GDD).
"""

from __future__ import annotations

import pandas as pd


def rolling_features(
    df: pd.DataFrame, column: str, windows: tuple[str, ...] = ("1h", "6h", "24h")
) -> pd.DataFrame:
    """Append rolling mean/std of `column` over the given time windows."""
    out = df.copy()
    for w in windows:
        out[f"{column}_mean_{w}"] = df[column].rolling(w).mean()
        out[f"{column}_std_{w}"] = df[column].rolling(w).std()
    return out


def lag_features(df: pd.DataFrame, column: str, lags: tuple[int, ...] = (1, 6, 24)) -> pd.DataFrame:
    """Append lagged copies of `column` (in rows of the regular grid)."""
    out = df.copy()
    for k in lags:
        out[f"{column}_lag_{k}"] = df[column].shift(k)
    return out


def growing_degree_days(temp: pd.Series, base: float = 10.0) -> pd.Series:
    """Cumulative GDD from a daily mean-temperature series (base 10 °C).

    GDD drives the harvest-timing model. Daily contribution = max(T - base, 0).
    """
    daily = temp.resample("1D").mean()
    return (daily - base).clip(lower=0).cumsum()

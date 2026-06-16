"""Naive and rule-based baselines. Nothing ships unless it beats these (D5)."""

from __future__ import annotations

import pandas as pd


def naive_persistence(series: pd.Series, horizon: int) -> pd.Series:
    """Predict the last observed value for every future step. The floor to beat."""
    return series.shift(horizon)


def threshold_rule(moisture: pd.Series, irrigate_below: float) -> pd.Series:
    """Fixed-threshold irrigation decision: irrigate when moisture < threshold."""
    return moisture < irrigate_below


# TODO(D2): arima.py (pmdarima.auto_arima), prophet.py, lstm.py (encoder-decoder,
# multi-task soil-moisture + temperature head). Walk-forward eval in vine.d5_evaluation.

"""Shared metrics. Pure functions, unit-tested, used by all tracks."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def mae(y_true: NDArray, y_pred: NDArray) -> float:
    """Mean absolute error."""
    return float(np.mean(np.abs(np.asarray(y_true) - np.asarray(y_pred))))


def rmse(y_true: NDArray, y_pred: NDArray) -> float:
    """Root mean squared error."""
    diff = np.asarray(y_true) - np.asarray(y_pred)
    return float(np.sqrt(np.mean(diff**2)))


def precision_recall(y_true: NDArray, y_pred: NDArray) -> tuple[float, float]:
    """Precision and recall for a boolean decision (e.g. irrigation trigger)."""
    yt = np.asarray(y_true, dtype=bool)
    yp = np.asarray(y_pred, dtype=bool)
    tp = int(np.sum(yt & yp))
    fp = int(np.sum(~yt & yp))
    fn = int(np.sum(yt & ~yp))
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    return precision, recall

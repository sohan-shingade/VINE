"""Shared metrics. Pure functions, unit-tested, used by all tracks."""

from __future__ import annotations

from typing import TypedDict

import numpy as np
from numpy.typing import NDArray


def mae(y_true: NDArray, y_pred: NDArray) -> float:
    """Mean absolute error."""
    return float(np.mean(np.abs(np.asarray(y_true) - np.asarray(y_pred))))


def rmse(y_true: NDArray, y_pred: NDArray) -> float:
    """Root mean squared error."""
    diff = np.asarray(y_true) - np.asarray(y_pred)
    return float(np.sqrt(np.mean(diff**2)))


class BinaryMetrics(TypedDict):
    """Counts and rates for one boolean decision."""

    true_negative: int
    false_positive: int
    false_negative: int
    true_positive: int
    precision: float
    recall: float
    f1: float
    specificity: float
    prevalence: float
    alert_rate: float


def confusion_counts(y_true: NDArray, y_pred: NDArray) -> tuple[int, int, int, int]:
    """Return ``(TN, FP, FN, TP)`` for equally shaped boolean arrays."""
    yt = np.asarray(y_true, dtype=bool)
    yp = np.asarray(y_pred, dtype=bool)
    if yt.shape != yp.shape:
        raise ValueError(f"shape mismatch: y_true{yt.shape} != y_pred{yp.shape}")
    tn = int(np.sum(~yt & ~yp))
    fp = int(np.sum(~yt & yp))
    fn = int(np.sum(yt & ~yp))
    tp = int(np.sum(yt & yp))
    return tn, fp, fn, tp


def binary_classification_metrics(y_true: NDArray, y_pred: NDArray) -> BinaryMetrics:
    """Return transparent counts and rates for a boolean decision.

    Rates with a zero denominator are reported as 0.0. ``prevalence`` is the
    observed-positive share; ``alert_rate`` is the predicted-positive share.
    """
    tn, fp, fn, tp = confusion_counts(y_true, y_pred)
    total = tn + fp + fn + tp
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    specificity = tn / (tn + fp) if (tn + fp) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "true_negative": tn,
        "false_positive": fp,
        "false_negative": fn,
        "true_positive": tp,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "specificity": specificity,
        "prevalence": (tp + fn) / total if total else 0.0,
        "alert_rate": (tp + fp) / total if total else 0.0,
    }


def precision_recall(y_true: NDArray, y_pred: NDArray) -> tuple[float, float]:
    """Precision and recall for a boolean decision (e.g. irrigation trigger)."""
    metrics = binary_classification_metrics(y_true, y_pred)
    return metrics["precision"], metrics["recall"]

"""Tests for shared evaluation metrics (D5)."""

import numpy as np
import pytest

from vine.d5_evaluation.metrics import (
    binary_classification_metrics,
    confusion_counts,
    mae,
    precision_recall,
    rmse,
)


def test_mae_and_rmse_zero_on_perfect():
    y = np.array([1.0, 2.0, 3.0])
    assert mae(y, y) == 0.0
    assert rmse(y, y) == 0.0


def test_rmse_penalizes_large_errors_more_than_mae():
    y_true = np.array([0.0, 0.0])
    y_pred = np.array([0.0, 10.0])
    assert rmse(y_true, y_pred) > mae(y_true, y_pred)


def test_precision_recall_basic():
    y_true = np.array([1, 1, 0, 0])
    y_pred = np.array([1, 0, 0, 0])
    p, r = precision_recall(y_true, y_pred)
    assert p == 1.0  # one predicted positive, correct
    assert r == 0.5  # caught one of two real positives


def test_confusion_counts_and_rates():
    y_true = np.array([1, 1, 0, 0])
    y_pred = np.array([1, 0, 1, 0])
    assert confusion_counts(y_true, y_pred) == (1, 1, 1, 1)
    metrics = binary_classification_metrics(y_true, y_pred)
    assert metrics == {
        "true_negative": 1,
        "false_positive": 1,
        "false_negative": 1,
        "true_positive": 1,
        "precision": 0.5,
        "recall": 0.5,
        "f1": 0.5,
        "specificity": 0.5,
        "prevalence": 0.5,
        "alert_rate": 0.5,
    }


def test_binary_metrics_handle_empty_positive_classes():
    metrics = binary_classification_metrics(np.zeros(3), np.zeros(3))
    assert metrics["precision"] == 0.0
    assert metrics["recall"] == 0.0
    assert metrics["specificity"] == 1.0
    assert metrics["prevalence"] == 0.0
    assert metrics["alert_rate"] == 0.0


def test_confusion_counts_reject_shape_mismatch():
    with pytest.raises(ValueError, match="shape mismatch"):
        confusion_counts(np.zeros(2), np.zeros(3))

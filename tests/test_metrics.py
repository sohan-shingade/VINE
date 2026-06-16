"""Tests for shared evaluation metrics (D5)."""

import numpy as np

from vine.d5_evaluation.metrics import mae, precision_recall, rmse


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

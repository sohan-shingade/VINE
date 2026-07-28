"""D5 — systematic evaluation. Every model is compared against simpler ones.

Shared metrics + walk-forward validation so the three tracks report results
the same way (the basis for the evaluation report and final blog post).
"""

from vine.d5_evaluation.metrics import (
    BinaryMetrics,
    binary_classification_metrics,
    confusion_counts,
    mae,
    precision_recall,
    rmse,
)
from vine.d5_evaluation.reporting import (
    Report,
    build_report,
    fold_assignment,
    fold_masks,
    holdout_mask,
)
from vine.d5_evaluation.walkforward import expanding_splits, skill, walk_forward

__all__ = [
    "BinaryMetrics",
    "Report",
    "binary_classification_metrics",
    "build_report",
    "confusion_counts",
    "expanding_splits",
    "fold_assignment",
    "fold_masks",
    "holdout_mask",
    "mae",
    "precision_recall",
    "rmse",
    "skill",
    "walk_forward",
]

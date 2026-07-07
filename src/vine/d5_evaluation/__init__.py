"""D5 — systematic evaluation. Every model is compared against simpler ones.

Shared metrics + walk-forward validation so the three tracks report results
the same way (the basis for the evaluation report and final blog post).
"""

from vine.d5_evaluation.metrics import mae, precision_recall, rmse
from vine.d5_evaluation.walkforward import expanding_splits, skill, walk_forward

__all__ = ["mae", "rmse", "precision_recall", "expanding_splits", "walk_forward", "skill"]

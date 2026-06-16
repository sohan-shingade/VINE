"""Harvest baseline: predict the same calendar date as last year per block."""

from __future__ import annotations

import pandas as pd


def last_year_date(historical: pd.DataFrame, block_id: str) -> pd.Timestamp | None:
    """Most recent recorded harvest date for a block. The baseline to beat (D5).

    `historical` columns: block_id, harvest_date.
    """
    rows = historical[historical["block_id"] == block_id]
    if rows.empty:
        return None
    return pd.to_datetime(rows["harvest_date"]).max()


# TODO(D4): xgboost.py (engineered tabular features), lstm.py (season sequence).

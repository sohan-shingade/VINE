"""Typed config for harvest experiments (validates configs/harvest/*.yaml)."""

from __future__ import annotations

from pydantic import BaseModel


class HarvestConfig(BaseModel):
    model: str = "xgboost"  # naive | xgboost | lstm
    target: str = "days_to_harvest"  # days_to_harvest | harvest_ready
    features: list[str] = ["gdd", "brix", "ndvi_trend", "soil_moisture", "weather"]
    # XGBoost knobs
    n_estimators: int = 300
    max_depth: int = 5
    lr: float = 0.05

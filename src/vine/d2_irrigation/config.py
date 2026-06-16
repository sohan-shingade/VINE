"""Typed config for irrigation experiments (validates configs/irrigation/*.yaml)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class IrrigationConfig(BaseModel):
    model: str = Field(description="naive | threshold | arima | prophet | lstm")
    horizons_h: list[int] = [6, 12, 24, 48]
    features: list[str] = ["soil_moisture", "temperature", "humidity"]
    # LSTM-only knobs (ignored by classical models)
    window_h: int = 72
    hidden: int = 128
    layers: int = 2
    lr: float = 1e-3
    epochs: int = 50
    # Decision layer: recommend irrigation when predicted moisture crosses this.
    irrigate_below: float = 25.0

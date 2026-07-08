"""Typed config for irrigation experiments (validates configs/d2_irrigation/*.yaml)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class IrrigationConfig(BaseModel):
    model: str = Field(
        description="naive | ridge | arima | forest | gbt implemented; prophet | lstm not built"
    )
    device: str = "SE01-LS-1"  # which sensor's snapshot to forecast
    target: str = "soil_water"  # column to forecast (a KIND_MEASUREMENTS name)
    features: list[str] = ["soil_water", "soil_temperature", "soil_conductivity"]
    horizons_h: list[int] = [6, 12, 24, 48]
    n_folds: int = 5  # walk-forward folds over the holdout half
    # Ridge-only knobs
    alpha: float = 1.0
    predict_delta: bool = False  # learn y(t) - y(t-h), reconstructed to level before scoring
    forecast_features: bool = False  # attach add_lead_time_features (perfect-forecast proxy)
    # ARIMA-only knobs
    order: list[int] = [2, 1, 2]
    # Tree-model knobs (forest / gbt)
    n_estimators: int = 300
    max_depth: int | None = None
    gbt_learning_rate: float = 0.06
    gbt_max_iter: int = 300
    # LSTM-only knobs (ignored by classical models)
    window_h: int = 72
    hidden: int = 128
    layers: int = 2
    lr: float = 1e-3
    epochs: int = 50
    # Decision layer: recommend irrigation when predicted moisture crosses this.
    irrigate_below: float = 25.0

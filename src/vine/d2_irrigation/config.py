"""Typed config for irrigation experiments (validates configs/d2_irrigation/*.yaml)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class IrrigationConfig(BaseModel):
    model: str = Field(
        description="naive | ridge | arima | forest | gbt | water_balance | prophet | lstm"
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
    # Where the `_next_{h}h` lead-time columns come from when forecast_features
    # is on: "oracle" = realized future weather (perfect-forecast upper bound),
    # "vintage" = real archived forecasts as issued (Open-Meteo previous runs).
    weather_source: Literal["oracle", "vintage"] = "oracle"
    # Water-balance-only knobs.
    wb_use_level: bool = False  # add current moisture level as a 3rd feature
    wb_gate_precip_mm: float | None = None  # apply correction only when rain > this
    wb_robust: bool = False  # Huber (robust) Δ-regression — tames storm overshoot
    wb_saturate_k: float | None = None  # cap correction at k × max observed |Δ|
    wb_adaptive_blend: bool = False  # shrink correction by recent training evidence
    wb_val_frac: float = Field(default=0.25, gt=0.0, lt=0.5)
    wb_blend_weights: tuple[float, ...] = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
    wb_min_fit_rows: int = Field(default=20, ge=5)
    wb_min_val_rows: int = Field(default=10, ge=5)
    wb_huber_max_iter: int = Field(default=500, ge=50)
    # ARIMA-only knobs
    order: list[int] = [2, 1, 2]
    # Prophet-only knobs: shifted feature columns fed as external regressors
    # (their value on the row for target time t is the reading at t-h).
    prophet_regressors: list[str] = ["soil_temperature"]
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
    batch_size: int = 128
    # Decision layer: recommend irrigation when predicted moisture crosses this.
    irrigate_below: float = 25.0

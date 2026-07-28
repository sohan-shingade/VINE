"""Pure irrigation-serving logic for the shipped D2 persistence model."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field


class IrrigationServingConfig(BaseModel):
    horizons_h: tuple[int, ...] = (6, 12, 24, 48)
    irrigate_below: float = 25.0
    max_age_h: float = Field(default=6.0, gt=0)
    block_devices: dict[str, str] = Field(default_factory=dict)


class HorizonForecast(BaseModel):
    horizon_h: int
    soil_water: float


class IrrigationForecast(BaseModel):
    block_id: str
    device_id: str
    observed_at: datetime
    latest_moisture: float
    unit: str = "sensor units"
    model: str = "persistence"
    forecast: list[HorizonForecast]
    irrigate_below: float
    recommend_irrigation: bool | None
    data_status: str
    age_hours: float
    reason: str


class UnknownBlockError(LookupError):
    """Requested block has no configured sensor."""


class NoReadingError(RuntimeError):
    """Configured sensor has no usable moisture reading."""


def build_irrigation_forecast(
    block_id: str,
    cfg: IrrigationServingConfig,
    load_device: Callable[[str], pd.DataFrame],
    *,
    now: datetime | None = None,
) -> IrrigationForecast:
    """Build a quality-aware persistence forecast from the newest valid reading."""
    if block_id not in cfg.block_devices:
        raise UnknownBlockError(block_id)
    device_id = cfg.block_devices[block_id]
    frame = load_device(device_id)
    if "soil_water" not in frame.columns:
        raise NoReadingError(f"{device_id}: soil_water column missing")
    moisture = pd.to_numeric(frame["soil_water"], errors="coerce")
    moisture = moisture[np.isfinite(moisture.to_numpy(dtype=float))].sort_index()
    if moisture.empty:
        raise NoReadingError(f"{device_id}: no finite soil_water readings")

    observed_at = pd.Timestamp(moisture.index[-1])
    if observed_at.tzinfo is None:
        observed_at = observed_at.tz_localize("UTC")
    else:
        observed_at = observed_at.tz_convert("UTC")
    current = float(moisture.iloc[-1])
    current_time = pd.Timestamp(now or datetime.now(UTC))
    if current_time.tzinfo is None:
        current_time = current_time.tz_localize("UTC")
    else:
        current_time = current_time.tz_convert("UTC")
    age_h = (current_time - observed_at).total_seconds() / 3600
    future = age_h < -0.25
    stale = age_h > cfg.max_age_h

    recommendation = None if stale or future else current < cfg.irrigate_below
    if future:
        status = "invalid"
        reason = f"latest reading is {-age_h:.1f} h in the future; recommendation suppressed"
    elif stale:
        status = "stale"
        reason = f"latest reading is {age_h:.1f} h old; recommendation suppressed"
    elif recommendation:
        status = "ok"
        reason = f"latest moisture is below the {cfg.irrigate_below:g} threshold"
    else:
        status = "ok"
        reason = f"latest moisture is at or above the {cfg.irrigate_below:g} threshold"
    return IrrigationForecast(
        block_id=block_id,
        device_id=device_id,
        observed_at=observed_at.to_pydatetime(),
        latest_moisture=current,
        forecast=[HorizonForecast(horizon_h=h, soil_water=current) for h in cfg.horizons_h],
        irrigate_below=cfg.irrigate_below,
        recommend_irrigation=recommendation,
        data_status=status,
        age_hours=age_h,
        reason=reason,
    )

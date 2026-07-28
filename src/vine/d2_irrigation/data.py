"""Load and normalize the five IHV soil probes used by D2 experiments."""

from __future__ import annotations

import pandas as pd

from vine.d1_pipeline.ingest import load_snapshot, load_weather_snapshot
from vine.d1_pipeline.pipeline import attach_weather, build_sensor_features

SOIL_DEVICES = ("SE01-LS-1", "SE01-LS-2", "SE01-LS-3", "SE01-LS-4", "SE0X-LS-1")
SOIL_FEATURES = ("soil_water", "soil_temperature", "soil_conductivity")
SE0X_COLUMNS = {
    "device_frmpayload_data_water_SOIL1": "soil_water",
    "device_frmpayload_data_temp_SOIL1": "soil_temperature",
    "device_frmpayload_data_conduct_SOIL1": "soil_conductivity",
}


def normalize_soil_probe(raw: pd.DataFrame, device: str) -> pd.DataFrame:
    """Return one probe frame with the shared soil-column schema.

    SE0X-LS-1 stores its first-depth channels under raw LoRa decoder names.
    Existing canonical columns take precedence if a snapshot contains both.
    Other devices are returned as an independent, otherwise unchanged frame.
    """
    frame = raw.copy()
    if device != "SE0X-LS-1":
        return frame
    for source, target in SE0X_COLUMNS.items():
        if source not in frame:
            continue
        if target in frame:
            frame = frame.drop(columns=source)
        else:
            frame = frame.rename(columns={source: target})
    return frame


def load_soil_probe_frames() -> dict[str, pd.DataFrame]:
    """Load, normalize, featurize, and weather-join all available soil probes."""
    weather = load_weather_snapshot()
    frames: dict[str, pd.DataFrame] = {}
    for device in SOIL_DEVICES:
        raw = normalize_soil_probe(load_snapshot(device), device)
        if "soil_water" not in raw:
            continue
        frame = build_sensor_features(raw, value_cols=list(SOIL_FEATURES))
        if weather is not None:
            frame = attach_weather(frame, weather)
        frames[device] = frame
    return frames

"""Shared five-probe loading and SE0X normalization tests (D2)."""

from __future__ import annotations

import pandas as pd

import vine.d2_irrigation.data as data


def test_normalize_se0x_maps_soil1_without_mutating_input():
    raw = pd.DataFrame(
        {
            "device_frmpayload_data_water_SOIL1": [18.0],
            "device_frmpayload_data_temp_SOIL1": [21.0],
            "device_frmpayload_data_conduct_SOIL1": [0.4],
            "other": [7.0],
        }
    )

    normalized = data.normalize_soil_probe(raw, "SE0X-LS-1")

    assert normalized.to_dict("list") == {
        "soil_water": [18.0],
        "soil_temperature": [21.0],
        "soil_conductivity": [0.4],
        "other": [7.0],
    }
    assert "device_frmpayload_data_water_SOIL1" in raw


def test_normalize_se0x_preserves_existing_canonical_column():
    raw = pd.DataFrame(
        {
            "soil_water": [25.0],
            "device_frmpayload_data_water_SOIL1": [18.0],
        }
    )

    normalized = data.normalize_soil_probe(raw, "SE0X-LS-1")

    assert normalized.columns.tolist() == ["soil_water"]
    assert normalized["soil_water"].tolist() == [25.0]


def test_load_soil_probe_frames_normalizes_and_weather_joins(monkeypatch):
    index = pd.date_range("2026-01-01", periods=2, freq="1h", tz="UTC")
    weather = pd.DataFrame({"precip_mm": [1.0]})
    loaded: list[str] = []
    feature_inputs: dict[str, list[str]] = {}

    def load_snapshot(device):
        loaded.append(device)
        if device == "SE01-LS-2":
            return pd.DataFrame({"air_temperature": [20.0, 21.0]}, index=index)
        if device == "SE0X-LS-1":
            return pd.DataFrame({"device_frmpayload_data_water_SOIL1": [18.0, 17.5]}, index=index)
        return pd.DataFrame({"soil_water": [25.0, 24.5]}, index=index)

    def build_features(raw, value_cols):
        feature_inputs[loaded[-1]] = list(raw.columns)
        return raw.assign(featured=True)

    monkeypatch.setattr(data, "load_snapshot", load_snapshot)
    monkeypatch.setattr(data, "load_weather_snapshot", lambda: weather)
    monkeypatch.setattr(data, "build_sensor_features", build_features)
    monkeypatch.setattr(
        data,
        "attach_weather",
        lambda frame, daily: frame.assign(weather_joined=daily is weather),
    )

    frames = data.load_soil_probe_frames()

    assert loaded == list(data.SOIL_DEVICES)
    assert set(frames) == set(data.SOIL_DEVICES) - {"SE01-LS-2"}
    assert feature_inputs["SE0X-LS-1"] == ["soil_water"]
    assert all(frame["featured"].all() for frame in frames.values())
    assert all(frame["weather_joined"].all() for frame in frames.values())

"""InfluxDB reader tests — Flux building + device-aware aliases (no network)."""

import pandas as pd
import pytest

from vine.d1_pipeline.influx import InfluxReader, build_flux, measurement_aliases


def test_build_flux_contains_device_and_pivot():
    q = build_flux("SE01-LS-1", ["device_frmpayload_data_temp_SOIL"], bucket="ihv")
    assert 'r["device_name"] == "SE01-LS-1"' in q
    assert 'from(bucket: "ihv")' in q
    assert "pivot(" in q


def test_build_flux_ors_multiple_measurements():
    q = build_flux("SE01-LS-1", ["a", "b"], bucket="ihv")
    assert 'r["_measurement"] == "a" or r["_measurement"] == "b"' in q


def test_build_flux_has_optional_stop_bound():
    q = build_flux(
        "EM500-PP-4842",
        ["device_frmpayload_data_pressure"],
        bucket="ihv",
        start="2026-07-01T00:00:00Z",
        stop="2026-07-02T00:00:00Z",
    )
    assert "range(start: 2026-07-01T00:00:00Z, stop: 2026-07-02T00:00:00Z)" in q


def test_pressure_alias_depends_on_device_context():
    raw = "device_frmpayload_data_pressure"
    assert measurement_aliases("EM500-CO2-915M-1")[raw] == "pressure"
    assert measurement_aliases("EM500-PP-4842")[raw] == "pipe_pressure_raw"


class _QueryApi:
    def __init__(self, frame):
        self.frame = frame
        self.query = ""

    def query_data_frame(self, *, org, query):
        self.query = query
        return self.frame.copy()


class _Client:
    def __init__(self, frame):
        self.api = _QueryApi(frame)
        self.closed = False

    def query_api(self):
        return self.api

    def close(self):
        self.closed = True


def test_reader_applies_pipe_pressure_alias_and_stop(monkeypatch):
    raw = "device_frmpayload_data_pressure"
    frame = pd.DataFrame(
        {"_time": ["2026-07-01T00:00:00Z"], raw: ["12.5"], "device_name": ["EM500-PP-4842"]}
    )
    client = _Client(frame)
    reader = InfluxReader(token="t")
    monkeypatch.setattr(reader, "_client", lambda: client)

    result = reader.read(
        "EM500-PP-4842",
        ["pressure"],
        start="2026-07-01T00:00:00Z",
        stop="2026-07-02T00:00:00Z",
    )

    assert result["pipe_pressure_raw"].iloc[0] == 12.5
    assert "pressure" not in result.columns
    assert "stop: 2026-07-02T00:00:00Z" in client.api.query
    assert client.closed


def test_reader_requires_token(monkeypatch):
    # Force empty config token so the guard fires regardless of local .env.
    monkeypatch.setattr("vine.d1_pipeline.influx.settings.influx_token", "", raising=False)
    with pytest.raises(ValueError, match="token"):
        InfluxReader(token="")


def test_reader_keeps_explicit_config():
    reader = InfluxReader(url="http://x", token="t", org="o", bucket="b")
    assert (reader.url, reader.token, reader.org, reader.bucket) == ("http://x", "t", "o", "b")

"""InfluxDB reader tests — Flux building + token guard (no network)."""

import pytest

from vine.d1_pipeline.influx import InfluxReader, build_flux


def test_build_flux_contains_device_and_pivot():
    q = build_flux("SE01-LS-1", ["device_frmpayload_data_temp_SOIL"], bucket="ihv")
    assert 'r["device_name"] == "SE01-LS-1"' in q
    assert 'from(bucket: "ihv")' in q
    assert "pivot(" in q


def test_build_flux_ors_multiple_measurements():
    q = build_flux("SE01-LS-1", ["a", "b"], bucket="ihv")
    assert 'r["_measurement"] == "a" or r["_measurement"] == "b"' in q


def test_reader_requires_token(monkeypatch):
    # Force empty config token so the guard fires regardless of local .env.
    monkeypatch.setattr("vine.d1_pipeline.influx.settings.influx_token", "", raising=False)
    with pytest.raises(ValueError, match="token"):
        InfluxReader(token="")


def test_reader_keeps_explicit_config():
    r = InfluxReader(url="http://x", token="t", org="o", bucket="b")
    assert (r.url, r.token, r.org, r.bucket) == ("http://x", "t", "o", "b")

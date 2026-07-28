"""Single-device ingestion and provenance-quality profile tests (no network)."""

import pandas as pd
import pytest

from vine.d1_pipeline.ingest import ingest_device, quality_profile


class _Reader:
    def __init__(self, frame):
        self.frame = frame
        self.call = None

    def read(self, device, measurements, start, *, stop):
        self.call = (device, measurements, start, stop)
        return self.frame.copy()


def test_ingest_device_is_bounded_and_records_provenance():
    frame = pd.DataFrame(
        {"pipe_pressure_raw": [12.0]},
        index=pd.to_datetime(["2026-07-01T00:00:00Z"]),
    )
    reader = _Reader(frame)

    result = ingest_device(
        "EM500-PP-4842",
        "2026-07-01T00:00:00Z",
        "2026-07-02T00:00:00Z",
        reader=reader,
    )

    assert reader.call == (
        "EM500-PP-4842",
        ["pressure"],
        "2026-07-01T00:00:00Z",
        "2026-07-02T00:00:00Z",
    )
    assert result.attrs == {
        "source": "influxdb",
        "device": "EM500-PP-4842",
        "device_kind": "pipe_pressure",
        "query_start": "2026-07-01T00:00:00Z",
        "query_stop": "2026-07-02T00:00:00Z",
        "units": {},
    }


def test_ingest_device_requires_known_device_and_stop_bound():
    reader = _Reader(pd.DataFrame())
    with pytest.raises(ValueError, match="stop bound"):
        ingest_device("EM500-PP-4842", "2026-07-01T00:00:00Z", reader=reader)
    with pytest.raises(ValueError, match="Unknown device"):
        ingest_device("mystery", "2026-07-01", "2026-07-02", reader=reader)
    assert reader.call is None


def test_quality_profile_preserves_provenance_and_blocks_unknown_unit():
    index = pd.to_datetime(["2026-07-01T00:00:00Z", "2026-07-01T02:00:00Z"])
    frame = pd.DataFrame({"pipe_pressure_raw": [12.0, 1_000_000.0]}, index=index)
    frame.attrs.update(
        source="influxdb",
        device="EM500-PP-4842",
        query_start="2026-07-01T00:00:00Z",
        query_stop="2026-07-02T00:00:00Z",
        units={},
    )

    row = quality_profile(frame).iloc[0]

    assert row["device"] == "EM500-PP-4842"
    assert row["source"] == "influxdb"
    assert row["query_start"] == "2026-07-01T00:00:00Z"
    assert row["query_stop"] == "2026-07-02T00:00:00Z"
    assert row["observations"] == 2
    assert row["missing_bins"] == 1
    assert pd.isna(row["unit"])
    assert pd.isna(row["out_of_range"])
    assert not row["physical_semantics"]

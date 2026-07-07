"""Imagery reader tests — filename parsing, capture grouping, flight index (no network)."""

import numpy as np

from vine.d1_pipeline import imagery
from vine.d1_pipeline.webdav import Entry

FLIGHT = "_sorted_data/BLOCKS/H5/2026-01-08/m3m/DJI_202601081523_001"


def _entry(name: str, size: int = imagery.MS_TIF_BYTES) -> Entry:
    return Entry(path=f"{FLIGHT}/{name}", is_dir=False, size=size)


def test_parse_capture_filename_bands_and_rgb():
    assert imagery.parse_capture_filename("DJI_20260108152708_0001_MS_G_point1.TIF") == (
        "20260108152708",
        "0001",
        "MS_G",
        1,
    )
    assert imagery.parse_capture_filename("DJI_20260108152708_0001_D_point1.JPG") == (
        "20260108152708",
        "0001",
        "D",
        1,
    )
    # PPK/RTK sidecars are not captures
    assert imagery.parse_capture_filename("DJI_202601081523_001_PPKNAV.nav") is None
    assert imagery.parse_capture_filename("DJI_202601081523_001_Timestamp.MRK") is None


def test_group_captures_one_trigger_five_files():
    names = [
        "DJI_20260108152708_0001_D_point1.JPG",
        "DJI_20260108152708_0001_MS_G_point1.TIF",
        "DJI_20260108152708_0001_MS_R_point1.TIF",
        "DJI_20260108152708_0001_MS_RE_point1.TIF",
        "DJI_20260108152708_0001_MS_NIR_point1.TIF",
        "DJI_20260108152711_0002_MS_G_point2.TIF",  # partial second capture
        "DJI_202601081523_001_PPKRAW.bin",  # ignored sidecar
    ]
    captures = imagery.group_captures(_entry(n) for n in names)
    assert len(captures) == 2
    first, second = captures
    assert first.seq == "0001" and first.point == 1
    assert set(first.bands) == {"green", "red", "red_edge", "nir"}
    assert first.rgb is not None and first.rgb.endswith("_D_point1.JPG")
    assert set(second.bands) == {"green"} and second.rgb is None


def test_index_flights_walks_share_placement(monkeypatch):
    client = imagery.ShareClient("https://nextcloud.example/s/tok")
    root = "_sorted_data/BLOCKS"
    tree = {
        root: [Entry(f"{root}/H5", True, 0), Entry(f"{root}/Q", True, 0)],
        f"{root}/H5": [
            Entry(f"{root}/H5/2026-01-08", True, 0),
            Entry(f"{root}/H5/.gitkeep", False, 0),
        ],
        f"{root}/Q": [],  # empty block folder — skipped for free
        f"{root}/H5/2026-01-08": [Entry(f"{root}/H5/2026-01-08/m3m", True, 0)],
        f"{root}/H5/2026-01-08/m3m": [
            Entry(f"{root}/H5/2026-01-08/m3m/DJI_202601081523_001", True, 0),
            Entry(f"{root}/H5/2026-01-08/m3m/images", True, 0),  # JPG copies — not a flight
        ],
    }
    monkeypatch.setattr(client, "ls", lambda path="": tree[path])
    index = imagery.index_flights(client)
    assert list(index) == ["DJI_202601081523_001"]
    flight = index["DJI_202601081523_001"]
    assert (flight.block, flight.date, flight.camera) == ("H5", "2026-01-08", "m3m")


def test_fetch_capture_rejects_short_download(tmp_path, monkeypatch):
    client = imagery.ShareClient("https://nextcloud.example/s/tok")
    capture = imagery.Capture(
        timestamp="20260108152708",
        seq="0001",
        point=1,
        bands={"green": f"{FLIGHT}/DJI_20260108152708_0001_MS_G_point1.TIF"},
        rgb=None,
    )

    def _fake_download(share_path, dest, skip_existing=True):
        dest = tmp_path / "short.TIF"
        dest.write_bytes(b"truncated")
        return dest

    monkeypatch.setattr(client, "download", _fake_download)
    try:
        imagery.fetch_capture(client, capture, tmp_path)
        raise AssertionError("expected OSError on short download")
    except OSError as e:
        assert "short download" in str(e)


def test_stack_channels_seven_channel_contract():
    ones = np.ones((2, 2), dtype=np.float32)
    bands = {k: ones for k in ("red", "green", "blue", "nir", "red_edge")}
    out = imagery.stack_channels(bands)
    assert out.shape == (7, 2, 2)
    assert out.dtype == np.float32
    # NDVI/NDRE of identical bands are 0
    assert np.allclose(out[5], 0.0) and np.allclose(out[6], 0.0)

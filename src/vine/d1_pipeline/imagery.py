"""Read multispectral drone imagery: raw M3M captures + Pix4D orthomosaics.

Two imagery products live on the NextCloud share (layout + evidence in
docs/data/imagery-share-layout.md):

1. **Raw captures** under `_sorted_data/BLOCKS/<Block>/<date>/{m3m,mini}/
   DJI_<YYYYMMDDHHMM>_<NNN>/` — per-photo files
   `DJI_<ts>_<seq>_<D|MS_G|MS_R|MS_RE|MS_NIR>_point<K>.<JPG|TIF>`.
   The M3M has G/R/RedEdge/NIR bands (no blue). STAC's asset hrefs are stale
   (flights were re-sorted between blocks), so discovery walks the share tree:
   flight-folder name + filename are the stable keys.
2. **Stitched Pix4DFields orthomosaics** under `GIS/` (`<Layer>.data.tif`,
   10-18 GB) with NDVI/NDRE already computed — read windowed per block
   (see vine.d1_pipeline.geo), never whole.

Filename parsing and capture grouping are pure; downloads go through
`webdav.ShareClient`. rasterio/rioxarray are lazy (`geo` extra).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

from vine.common.logging import get_logger
from vine.d1_pipeline.indices import ndre, ndvi
from vine.d1_pipeline.webdav import Entry, ShareClient

if TYPE_CHECKING:
    import xarray as xr

log = get_logger(__name__)

# Band order in a stitched orthomosaic. Adjust to match the actual export.
BANDS = ("red", "green", "blue", "nir", "red_edge")

# Every M3M multispectral TIF is exactly this many bytes — integrity check.
MS_TIF_BYTES = 10_087_424

# M3M filename tags -> band names used across D1.
_BAND_BY_TAG = {"MS_G": "green", "MS_R": "red", "MS_RE": "red_edge", "MS_NIR": "nir"}

# DJI_20260108152708_0001_MS_G_point1.TIF / DJI_..._0001_D_point1.JPG
_CAPTURE_RE = re.compile(
    r"DJI_(\d{14})_(\d{4})_(D|MS_G|MS_R|MS_RE|MS_NIR)_point(\d+)\.(?:JPG|TIF)$"
)
# Flight folders: DJI_<YYYYMMDDHHMM>_<take> (occasionally with a trailing label)
_FLIGHT_RE = re.compile(r"DJI_\d{12}_\d{3}")


@dataclass(frozen=True)
class Capture:
    """One camera trigger: 4 multispectral TIFs + an RGB JPG, by share path."""

    timestamp: str  # YYYYMMDDHHMMSS
    seq: str  # 4-digit sequence within the flight
    point: int  # UgCS mission waypoint id
    bands: dict[str, str]  # band name -> share path (green/red/red_edge/nir)
    rgb: str | None  # _D JPG share path, if present


@dataclass(frozen=True)
class Flight:
    """One flight folder as placed in the share tree (block per the share, not STAC)."""

    folder: str  # DJI_YYYYMMDDHHMM_NNN
    block: str
    date: str  # YYYY-MM-DD folder name
    camera: str  # m3m | mini
    path: str  # share path of the flight folder


def parse_capture_filename(name: str) -> tuple[str, str, str, int] | None:
    """Parse a capture filename into (timestamp, seq, tag, point); None if not one.

    PPK/RTK sidecars (`*_PPKNAV.nav`, `*_Timestamp.MRK`, ...) parse as None.
    """
    m = _CAPTURE_RE.search(name)
    if m is None:
        return None
    ts, seq, tag, point = m.group(1), m.group(2), m.group(3), int(m.group(4))
    return ts, seq, tag, point


def group_captures(entries: Iterable[Entry]) -> list[Capture]:
    """Group a flight folder's files into per-trigger captures (pure).

    Keyed by (timestamp, seq); band files land in `bands`, the `_D` JPG in
    `rgb`. Non-capture files (PPK sidecars) are ignored.
    """
    grouped: dict[tuple[str, str], dict] = {}
    for e in entries:
        parsed = parse_capture_filename(Path(e.path).name)
        if parsed is None or e.is_dir:
            continue
        ts, seq, tag, point = parsed
        slot = grouped.setdefault((ts, seq), {"point": point, "bands": {}, "rgb": None})
        if tag == "D":
            slot["rgb"] = e.path
        else:
            slot["bands"][_BAND_BY_TAG[tag]] = e.path
    return [
        Capture(timestamp=ts, seq=seq, point=s["point"], bands=s["bands"], rgb=s["rgb"])
        for (ts, seq), s in sorted(grouped.items())
    ]


def index_flights(client: ShareClient, root: str = "_sorted_data/BLOCKS") -> dict[str, Flight]:
    """Sweep the share tree into {flight_folder -> Flight} (~60 cheap PROPFINDs).

    The share's block placement is authoritative (STAC's is stale). Blocks with
    no date folders are skipped for free — `ls` just returns their `.gitkeep`.
    """
    index: dict[str, Flight] = {}
    for block in (e for e in client.ls(root) if e.is_dir):
        for date in (e for e in client.ls(block.path) if e.is_dir):
            for camera in (e for e in client.ls(date.path) if e.is_dir):
                cam = Path(camera.path).name
                if cam not in ("m3m", "mini"):
                    continue
                for sub in (e for e in client.ls(camera.path) if e.is_dir):
                    name = Path(sub.path).name
                    m = _FLIGHT_RE.match(name)
                    if m is None:
                        continue  # e.g. the images/ JPG-copy folder
                    index[m.group(0)] = Flight(
                        folder=m.group(0),
                        block=Path(block.path).name,
                        date=Path(date.path).name,
                        camera=cam,
                        path=sub.path,
                    )
    log.info("indexed flights", flights=len(index))
    return index


def fetch_capture(
    client: ShareClient, capture: Capture, dest_dir: str | Path, rgb: bool = False
) -> dict[str, Path]:
    """Download one capture's band TIFs (and optionally the RGB JPG) to `dest_dir`.

    Returns {band name -> local path}. Multispectral TIFs are size-checked
    against the camera's fixed frame size — a short read is a failed download.
    """
    dest_dir = Path(dest_dir)
    local: dict[str, Path] = {}
    for band, share_path in sorted(capture.bands.items()):
        path = client.download(share_path, dest_dir / Path(share_path).name)
        if path.stat().st_size != MS_TIF_BYTES:
            raise OSError(f"short download ({path.stat().st_size} B): {share_path}")
        local[band] = path
    if rgb and capture.rgb is not None:
        local["rgb"] = client.download(capture.rgb, dest_dir / Path(capture.rgb).name)
    return local


def read_band(path: str | Path) -> NDArray:
    """Read a single-band TIF (one M3M band file) as a float32 array."""
    import rasterio

    with rasterio.open(path) as src:
        return src.read(1).astype(np.float32)


def read_orthomosaic(path: str | Path) -> xr.DataArray:
    """Load a multispectral GeoTIFF as an (band, y, x) DataArray."""
    import rioxarray  # noqa: F401  (registers the .rio accessor)
    import xarray as xr

    return xr.open_dataarray(path, engine="rasterio")


def stack_channels(bands: dict[str, NDArray]) -> NDArray:
    """Build the 7-channel CV input from a dict of named bands.

    Returns array shaped (7, H, W): R, G, B, NIR, RedEdge, NDVI, NDRE.
    Raw M3M captures have no blue band — pass `blue=green` or a zeros
    array explicitly if stacking per-photo bands; orthomosaics have all five.
    """
    r, g, b = bands["red"], bands["green"], bands["blue"]
    nir, re_ = bands["nir"], bands["red_edge"]
    return np.stack([r, g, b, nir, re_, ndvi(nir, r), ndre(nir, re_)]).astype(np.float32)

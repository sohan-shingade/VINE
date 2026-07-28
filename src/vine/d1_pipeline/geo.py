"""Register imagery and sensors to vineyard-block geometry (D1 block alignment).

Health scores and predictions are reported per vineyard block. Block polygons
(and sensor locations) live in `GIS/IHV-2026-05-26.kmz` on the NextCloud share:
39 block polygons whose names match `_sorted_data/BLOCKS/` 1:1, plus 182 point
placemarks including the LoRaWAN sensors (see docs/data/imagery-share-layout.md).

KML parsing is stdlib (the tags are namespaced — KML drivers vary by install,
ElementTree doesn't). Geometry work needs the `geo` extra (geopandas/shapely/
rasterio), imported lazily.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from vine.common.logging import get_logger

if TYPE_CHECKING:
    import geopandas as gpd

log = get_logger(__name__)

_KML = {"k": "http://www.opengis.net/kml/2.2"}


def parse_kml_placemarks(kml_text: str) -> list[dict]:
    """Extract named Polygon/Point placemarks from KML (pure, stdlib only).

    Returns dicts with `name`, `kind` ("polygon" | "point"), and `coords` —
    a list of (lon, lat) tuples (one tuple for points, the outer ring for
    polygons). Placemarks with other geometry are skipped.
    """
    root = ET.fromstring(kml_text)
    out: list[dict] = []
    for pm in root.iter(f"{{{_KML['k']}}}Placemark"):
        name = pm.findtext("k:name", "", _KML).strip()
        poly = pm.find(".//k:Polygon//k:LinearRing/k:coordinates", _KML)
        point = pm.find(".//k:Point/k:coordinates", _KML)
        node, kind = (poly, "polygon") if poly is not None else (point, "point")
        text = (node.text or "") if node is not None else ""
        if not text.strip():
            continue
        coords = [(float(lon), float(lat)) for lon, lat, *_ in (c.split(",") for c in text.split())]
        out.append({"name": name, "kind": kind, "coords": coords})
    return out


def load_blocks_kmz(path: str | Path) -> gpd.GeoDataFrame:
    """Load vineyard-block polygons from the IHV KMZ as a GeoDataFrame.

    Rows: `block_id` + WGS84 polygon geometry — one per block placemark.
    Point placemarks (sensors, photos) are skipped; see `load_points_kmz`.
    """
    import geopandas as gpd
    from shapely.geometry import Polygon

    marks = parse_kml_placemarks(_read_kmz(path))
    polys = [m for m in marks if m["kind"] == "polygon"]
    blocks = gpd.GeoDataFrame(
        {"block_id": [m["name"] for m in polys]},
        geometry=[Polygon(m["coords"]) for m in polys],
        crs="EPSG:4326",
    )
    log.info("loaded blocks", path=str(path), blocks=len(blocks))
    return blocks


def load_points_kmz(path: str | Path) -> gpd.GeoDataFrame:
    """Load point placemarks (sensor locations, field photos) from the IHV KMZ."""
    import geopandas as gpd
    from shapely.geometry import Point

    marks = parse_kml_placemarks(_read_kmz(path))
    pts = [m for m in marks if m["kind"] == "point"]
    return gpd.GeoDataFrame(
        {"name": [m["name"] for m in pts]},
        geometry=[Point(m["coords"][0]) for m in pts],
        crs="EPSG:4326",
    )


def _read_kmz(path: str | Path) -> str:
    """KMZ is a zip holding doc.kml (plus media); plain .kml reads directly."""
    path = Path(path)
    if path.suffix.lower() == ".kmz":
        with zipfile.ZipFile(path) as z:
            return z.read("doc.kml").decode()
    return path.read_text()


def load_blocks(path: str | Path) -> gpd.GeoDataFrame:
    """Load vineyard-block polygons (GeoJSON/Shapefile) with a `block_id`."""
    import geopandas as gpd

    blocks = gpd.read_file(path)
    if "block_id" not in blocks.columns:
        raise ValueError("block geometry must contain a 'block_id' column")
    return blocks


def zonal_stats(raster_path: str | Path, blocks: gpd.GeoDataFrame, band: int = 1) -> pd.DataFrame:
    """Per-block mean/std/count of one raster band, indexed by `block_id`.

    Reads windowed per polygon (`rasterio.mask` with crop) so 10+ GB Pix4D
    orthomosaics are never loaded whole. Blocks are reprojected to the raster
    CRS; raster nodata is excluded. Blocks that miss the raster get count 0.
    """
    import numpy as np
    import rasterio
    import rasterio.mask

    rows = []
    with rasterio.open(raster_path) as src:
        aligned = blocks.to_crs(src.crs)
        for block_id, geom in zip(aligned["block_id"], aligned.geometry, strict=True):
            try:
                data, _ = rasterio.mask.mask(src, [geom], crop=True, indexes=band, filled=False)
            except ValueError:  # polygon outside the raster extent
                rows.append({"block_id": block_id, "mean": np.nan, "std": np.nan, "count": 0})
                continue
            valid = data.compressed()  # drops mask + nodata
            rows.append(
                {
                    "block_id": block_id,
                    "mean": float(valid.mean()) if valid.size else np.nan,
                    "std": float(valid.std()) if valid.size else np.nan,
                    "count": int(valid.size),
                }
            )
    return pd.DataFrame(rows).set_index("block_id")


def zonal_distribution(
    raster_path: str | Path,
    blocks: gpd.GeoDataFrame,
    *,
    band: int = 1,
    quantiles: tuple[float, ...] = (0.1, 0.25, 0.5, 0.75),
    low_threshold: float | None = None,
) -> pd.DataFrame:
    """Windowed per-block distribution summaries for one raster band.

    The raster is opened once and each polygon is read with ``crop=True``; giant
    orthomosaics and range-backed URLs are never loaded whole. ``coverage`` is
    the fraction of polygon-interior pixels that are valid after nodata handling.
    """
    import numpy as np
    import rasterio
    import rasterio.features
    import rasterio.mask

    if any(q < 0.0 or q > 1.0 for q in quantiles):
        raise ValueError("quantiles must be between 0 and 1")
    rows = []
    with rasterio.open(raster_path) as src:
        aligned = blocks.to_crs(src.crs)
        for block_id, geom in zip(aligned["block_id"], aligned.geometry, strict=True):
            try:
                data, transform = rasterio.mask.mask(
                    src, [geom], crop=True, indexes=band, filled=False
                )
                interior = rasterio.features.geometry_mask(
                    [geom],
                    out_shape=data.shape,
                    transform=transform,
                    invert=True,
                )
            except ValueError:
                data = np.ma.array([], mask=[])
                interior = np.array([], dtype=bool)
            valid = data.compressed()
            total = int(interior.sum())
            row: dict[str, object] = {
                "block_id": block_id,
                "count": int(valid.size),
                "coverage": float(valid.size / total) if total else 0.0,
                "mean": float(valid.mean()) if valid.size else np.nan,
                "std": float(valid.std()) if valid.size else np.nan,
            }
            for q in quantiles:
                row[f"q{round(q * 100):02d}"] = (
                    float(np.quantile(valid, q)) if valid.size else np.nan
                )
            row["iqr"] = (
                float(np.quantile(valid, 0.75) - np.quantile(valid, 0.25)) if valid.size else np.nan
            )
            if low_threshold is not None:
                row["fraction_below"] = (
                    float(np.mean(valid < low_threshold)) if valid.size else np.nan
                )
            rows.append(row)
    return pd.DataFrame(rows).set_index("block_id")


def assign_sensors_to_blocks(points: gpd.GeoDataFrame, blocks: gpd.GeoDataFrame) -> pd.DataFrame:
    """Spatially join point locations to the block containing them.

    Returns the points frame plus a `block_id` column (NaN when a point falls
    outside every block — e.g. the office weather station).
    """
    import geopandas as gpd

    joined = gpd.sjoin(
        points, blocks[["block_id", "geometry"]].to_crs(points.crs), how="left", predicate="within"
    )
    return pd.DataFrame(joined.drop(columns=["index_right", "geometry"]))

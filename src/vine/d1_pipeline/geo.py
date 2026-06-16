"""Register imagery to vineyard-block geometry for per-block aggregation.

Health scores and predictions are reported per vineyard block, so imagery and
sensors must be tied to block polygons. Requires the `geo` extra (geopandas).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import geopandas as gpd


def load_blocks(path: str | Path) -> gpd.GeoDataFrame:
    """Load vineyard-block polygons (GeoJSON/Shapefile) with a `block_id`."""
    import geopandas as gpd

    blocks = gpd.read_file(path)
    if "block_id" not in blocks.columns:
        raise ValueError("block geometry must contain a 'block_id' column")
    return blocks


# TODO(D1): zonal_stats(raster, blocks) -> per-block mean NDVI/NDRE.
# TODO(D1): assign_sensors_to_blocks(sensors, blocks) via spatial join.

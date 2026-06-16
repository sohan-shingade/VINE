"""Read multispectral drone orthomosaics and tile them into model patches.

Imagery is GeoTIFF with RGB + NIR + Red-edge bands, georeferenced to vineyard
coordinates. The CV track consumes 7-channel patches: [R, G, B, NIR, RedEdge,
NDVI, NDRE].

Requires the `geo` extra (rasterio/rioxarray). Imported lazily so the core
package installs without the heavy geospatial stack.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

from vine.d1_pipeline.indices import ndre, ndvi

if TYPE_CHECKING:
    import xarray as xr

# Band order in the source orthomosaic. Adjust to match the actual sensor.
BANDS = ("red", "green", "blue", "nir", "red_edge")


def read_orthomosaic(path: str | Path) -> xr.DataArray:
    """Load a multispectral GeoTIFF as an (band, y, x) DataArray."""
    import rioxarray  # noqa: F401  (registers the .rio accessor)
    import xarray as xr

    return xr.open_dataarray(path, engine="rasterio")


def stack_channels(bands: dict[str, NDArray]) -> NDArray:
    """Build the 7-channel CV input from a dict of named bands.

    Returns array shaped (7, H, W): R, G, B, NIR, RedEdge, NDVI, NDRE.
    """
    r, g, b = bands["red"], bands["green"], bands["blue"]
    nir, re = bands["nir"], bands["red_edge"]
    return np.stack([r, g, b, nir, re, ndvi(nir, r), ndre(nir, re)]).astype(np.float32)

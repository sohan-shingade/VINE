"""Vegetation indices computed from multispectral bands.

Pure NumPy functions — no I/O, fully unit-tested. These quantify plant health
from drone imagery and feed both the CV track (extra channels) and the harvest
track (NDVI trend features).

NDVI = (NIR - Red) / (NIR + Red)            healthy canopy -> high NDVI
NDRE = (NIR - RedEdge) / (NIR + RedEdge)    more sensitive to chlorophyll
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

_EPS = 1e-8  # guard against divide-by-zero on no-data / shadow pixels


def _normalized_difference(a: NDArray, b: NDArray) -> NDArray:
    """(a - b) / (a + b), clipped to [-1, 1], NaN-safe."""
    a = a.astype(np.float32)
    b = b.astype(np.float32)
    out = (a - b) / (a + b + _EPS)
    return np.clip(out, -1.0, 1.0)


def ndvi(nir: NDArray, red: NDArray) -> NDArray:
    """Normalized Difference Vegetation Index."""
    return _normalized_difference(nir, red)


def ndre(nir: NDArray, red_edge: NDArray) -> NDArray:
    """Normalized Difference Red-Edge index."""
    return _normalized_difference(nir, red_edge)

"""Tests for vegetation indices — the pure core of the D1 pipeline."""

import numpy as np

from vine.d1_pipeline.indices import ndre, ndvi


def test_ndvi_healthy_vegetation_is_positive():
    # High NIR, low Red -> healthy canopy -> NDVI near 1.
    nir = np.array([0.8, 0.9])
    red = np.array([0.1, 0.05])
    out = ndvi(nir, red)
    assert np.all(out > 0.6)


def test_ndvi_bare_soil_near_zero():
    nir = np.array([0.3])
    red = np.array([0.3])
    assert abs(ndvi(nir, red)[0]) < 1e-3


def test_indices_bounded_in_range():
    rng = np.random.default_rng(0)
    a, b = rng.random((100,)), rng.random((100,))
    for out in (ndvi(a, b), ndre(a, b)):
        assert out.min() >= -1.0 and out.max() <= 1.0


def test_zero_division_is_safe():
    # All-zero pixels (no-data) must not raise or produce inf/nan.
    z = np.zeros(5)
    out = ndvi(z, z)
    assert np.all(np.isfinite(out))

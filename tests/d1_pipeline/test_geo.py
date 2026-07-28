"""Block-geometry tests — KML parsing, KMZ loading, zonal stats, sensor join.

Uses tiny synthetic geometries/rasters; needs the `geo` extra (as `make setup`
installs). The KML fixture uses an explicit namespace prefix like the real
IHV KMZ (whose tags are `ns0:`-prefixed — a plain-tag parser would find nothing).
"""

import zipfile

import numpy as np
import pytest

from vine.d1_pipeline import geo

KML = """<?xml version="1.0"?>
<ns0:kml xmlns:ns0="http://www.opengis.net/kml/2.2"><ns0:Document>
  <ns0:Placemark>
    <ns0:name>H5</ns0:name>
    <ns0:Polygon><ns0:outerBoundaryIs><ns0:LinearRing><ns0:coordinates>
      -122.90,38.45,0 -122.89,38.45,0 -122.89,38.46,0 -122.90,38.46,0 -122.90,38.45,0
    </ns0:coordinates></ns0:LinearRing></ns0:outerBoundaryIs></ns0:Polygon>
  </ns0:Placemark>
  <ns0:Placemark>
    <ns0:name>SE01-LS-2</ns0:name>
    <ns0:Point><ns0:coordinates>-122.895,38.455,0</ns0:coordinates></ns0:Point>
  </ns0:Placemark>
  <ns0:Placemark><ns0:name>no geometry</ns0:name></ns0:Placemark>
</ns0:Document></ns0:kml>"""


def test_parse_kml_placemarks_polygon_and_point():
    marks = geo.parse_kml_placemarks(KML)
    assert [(m["name"], m["kind"]) for m in marks] == [("H5", "polygon"), ("SE01-LS-2", "point")]
    poly, point = marks
    assert poly["coords"][0] == (-122.90, 38.45)  # (lon, lat), alt dropped
    assert len(poly["coords"]) == 5
    assert point["coords"] == [(-122.895, 38.455)]


@pytest.fixture
def kmz(tmp_path):
    path = tmp_path / "ihv.kmz"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("doc.kml", KML)
    return path


def test_load_blocks_kmz(kmz):
    blocks = geo.load_blocks_kmz(kmz)
    assert list(blocks["block_id"]) == ["H5"]
    assert blocks.crs.to_epsg() == 4326
    assert blocks.geometry.iloc[0].is_valid


def test_assign_sensors_to_blocks(kmz):
    blocks = geo.load_blocks_kmz(kmz)
    points = geo.load_points_kmz(kmz)
    out = geo.assign_sensors_to_blocks(points, blocks)
    assert out.loc[out["name"] == "SE01-LS-2", "block_id"].iloc[0] == "H5"


def test_zonal_stats_windowed_means(tmp_path, kmz):
    rasterio = pytest.importorskip("rasterio")
    from rasterio.transform import from_bounds

    # 10x10 raster spanning the H5 test square; left half 1.0, right half 3.0
    data = np.ones((10, 10), dtype=np.float32)
    data[:, 5:] = 3.0
    path = tmp_path / "toy.tif"
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=10,
        width=10,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=from_bounds(-122.90, 38.45, -122.89, 38.46, 10, 10),
    ) as dst:
        dst.write(data, 1)

    blocks = geo.load_blocks_kmz(kmz)
    stats = geo.zonal_stats(path, blocks)
    assert stats.loc["H5", "count"] == 100  # block covers the whole toy raster
    assert stats.loc["H5", "mean"] == pytest.approx(2.0)

    # a block entirely outside the raster gets count 0, NaN mean
    outside = blocks.copy()
    outside["geometry"] = outside.geometry.translate(xoff=1.0)
    stats = geo.zonal_stats(path, outside)
    assert stats.loc["H5", "count"] == 0
    assert np.isnan(stats.loc["H5", "mean"])


def test_zonal_distribution_low_tail_and_coverage(tmp_path, kmz):
    rasterio = pytest.importorskip("rasterio")
    from rasterio.transform import from_bounds

    data = np.linspace(0.1, 0.9, 100, dtype=np.float32).reshape(10, 10)
    path = tmp_path / "indices.tif"
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=10,
        width=10,
        count=1,
        dtype="float32",
        nodata=-9999,
        crs="EPSG:4326",
        transform=from_bounds(-122.90, 38.45, -122.89, 38.46, 10, 10),
    ) as dst:
        dst.write(data, 1)

    blocks = geo.load_blocks_kmz(kmz)
    stats = geo.zonal_distribution(path, blocks, quantiles=(0.1, 0.5), low_threshold=0.4)
    assert stats.loc["H5", "count"] == 100
    assert stats.loc["H5", "coverage"] == pytest.approx(1.0)
    assert stats.loc["H5", "q10"] == pytest.approx(np.quantile(data, 0.1))
    assert stats.loc["H5", "q50"] == pytest.approx(np.quantile(data, 0.5))
    assert stats.loc["H5", "fraction_below"] == pytest.approx(float(np.mean(data < 0.4)))
    assert stats.loc["H5", "iqr"] == pytest.approx(
        np.quantile(data, 0.75) - np.quantile(data, 0.25)
    )


def _write_index_raster(path, data, *, nodata=-9999):
    import rasterio
    from rasterio.transform import from_origin

    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=data.shape[0],
        width=data.shape[1],
        count=1,
        dtype="float32",
        nodata=nodata,
        crs="EPSG:4326",
        transform=from_origin(0, data.shape[0], 1, 1),
    ) as dst:
        dst.write(data.astype(np.float32), 1)


def _irregular_block():
    geopandas = pytest.importorskip("geopandas")
    from shapely.geometry import Polygon

    # An L-shaped 12-pixel polygon inside its 4x4 (16-pixel) bounding box.
    geometry = Polygon([(0, 0), (4, 0), (4, 2), (2, 2), (2, 4), (0, 4)])
    return geopandas.GeoDataFrame({"block_id": ["L"]}, geometry=[geometry], crs="EPSG:4326")


def test_zonal_distribution_full_coverage_uses_polygon_interior(tmp_path):
    pytest.importorskip("rasterio")
    path = tmp_path / "irregular-full.tif"
    _write_index_raster(path, np.ones((4, 4), dtype=np.float32))

    stats = geo.zonal_distribution(path, _irregular_block())

    assert stats.loc["L", "count"] == 12
    assert stats.loc["L", "coverage"] == pytest.approx(1.0)


def test_zonal_distribution_partial_nodata_uses_polygon_interior(tmp_path):
    pytest.importorskip("rasterio")
    data = np.ones((4, 4), dtype=np.float32)
    data[0, :2] = -9999  # two nodata pixels inside the L, none in its excluded corner
    path = tmp_path / "irregular-partial.tif"
    _write_index_raster(path, data)

    stats = geo.zonal_distribution(path, _irregular_block())

    assert stats.loc["L", "count"] == 10
    assert stats.loc["L", "coverage"] == pytest.approx(10 / 12)


def test_zonal_distribution_rejects_invalid_quantile(tmp_path, kmz):
    blocks = geo.load_blocks_kmz(kmz)
    with pytest.raises(ValueError, match="quantiles"):
        geo.zonal_distribution(tmp_path / "unused.tif", blocks, quantiles=(1.1,))

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

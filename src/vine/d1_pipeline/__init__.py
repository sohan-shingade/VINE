"""D1 — shared data ingestion & feature pipeline.

All three model tracks consume the outputs of this package so feature
engineering is written once. Submodules:

    sensors     read + resample LoRaWAN sensor time-series
    webdav      NextCloud public-share client (imagery transport)
    imagery     raw M3M captures + Pix4D orthomosaics from the share
    indices     vegetation indices (NDVI, NDRE) — pure functions
    geo         block polygons (KMZ), zonal stats, sensor→block join
    weather     historical weather from the Open-Meteo archive (ERA5)
    features    time-series feature engineering (rolling stats, GDD, lags)
    validation  range checks, gap detection, staleness flags
    pipeline    assemble the processed sensor feature table (sensor path)
"""

from vine.d1_pipeline.geo import assign_sensors_to_blocks, load_blocks_kmz, zonal_stats
from vine.d1_pipeline.imagery import fetch_capture, group_captures, index_flights
from vine.d1_pipeline.indices import ndre, ndvi
from vine.d1_pipeline.influx import InfluxReader
from vine.d1_pipeline.ndp import NDPClient
from vine.d1_pipeline.pipeline import attach_weather, build_sensor_features
from vine.d1_pipeline.weather import fetch_historical
from vine.d1_pipeline.webdav import ShareClient

__all__ = [
    "ndvi",
    "ndre",
    "NDPClient",
    "InfluxReader",
    "ShareClient",
    "fetch_historical",
    "build_sensor_features",
    "attach_weather",
    "index_flights",
    "group_captures",
    "fetch_capture",
    "load_blocks_kmz",
    "zonal_stats",
    "assign_sensors_to_blocks",
]

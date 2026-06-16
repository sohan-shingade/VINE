"""D1 — shared data ingestion & feature pipeline.

All three model tracks consume the outputs of this package so feature
engineering is written once. Submodules:

    sensors     read + resample LoRaWAN sensor time-series
    imagery     read multispectral GeoTIFF orthomosaics, tile into patches
    indices     vegetation indices (NDVI, NDRE) — pure functions
    geo         register imagery to vineyard-block geometry
    features    time-series feature engineering (rolling stats, GDD, lags)
    validation  range checks, gap detection, staleness flags
"""

from vine.d1_pipeline.indices import ndre, ndvi
from vine.d1_pipeline.influx import InfluxReader
from vine.d1_pipeline.ndp import NDPClient

__all__ = ["ndvi", "ndre", "NDPClient", "InfluxReader"]

# Data datasheet

Following the [*Datasheets for Datasets*](https://arxiv.org/abs/1803.09010)
(Gebru et al.) structure. Many fields are still **TBD**: confirm them with the
mentor during community bonding. The proposal notes the data pipeline may be
partially built.

## Motivation
- **Purpose:** train ML models for irrigation scheduling, plant-health
  assessment, and harvest timing at Iron Horse Vineyards.
- **Created by / for:** CENIC, UC San Diego, and partners; the VINE project.
- **Where it lives:** the live source is InfluxDB (sensors → ThingsBoard →
  InfluxDB bucket `ihv`), pulled with `vine.d1_pipeline.InfluxReader`, landed in
  `data/raw/`, and pinned with DVC ([ADR-0008](../adr/0008-sensor-source-influxdb.md)).
  The [National Data Platform](https://nationaldataplatform.org) is the intended
  *publishing* layer for shareable exports. Its catalog API is not yet
  confirmed ([ADR-0006](../adr/0006-ndp-data-access.md)), so don't treat it as
  the live source.

## Composition

| Source | Format | Fields | Cadence | Index |
|--------|--------|--------|---------|-------|
| LoRaWAN sensors → ThingsBoard → **InfluxDB** | Flux query (time-series DB) | soil conductivity/temp/water, CO₂, humidity, temperature, pressure | per device report (irregular) | `device_name` + UTC `_time` |
| Drone imagery | GeoTIFF (multispectral) | RGB, NIR, Red-edge bands | periodic flights (weather-dependent) | georeferenced raster |
| Historical records | CSV (TBD) | past harvest dates, yields, irrigation schedules | multi-year | per vineyard block |
| Weather (historical + forecast) | API (JSON) | tmax/tmin, precip, ET₀, GDD inputs | daily | vineyard lat/lon (38.457, −122.896) |

**Sources located (2026-06-16):** sensors in InfluxDB; imagery on NextCloud +
STAC (9,295 DJI M3M captures, 11 flights Aug 2025 to Jan 2026, RGB + green/red/
rededge/nir); weather from the Open-Meteo archive (ET₀ included) or
[gridMET](https://www.drought.gov/data-maps-tools/gridded-surface-meteorological-gridmet-dataset),
forecast via Open-Meteo/python-awips ([ADR-0009](../adr/0009-weather-data-sources.md)).
**Fresh record search (2026-07-23):** no harvest dates, yield, Brix, pH/TA,
or irrigation logs were found in the checked local/DVC snapshots, live InfluxDB,
NDP catalog, or current NextCloud share. These records still require a
vineyard/mentor handoff; D4 remains not evaluated.

**Sensor devices (IHV deployment):** `SE01-LS-1..4` (soil: conductivity,
temperature, water), `SE0X-LS-1` (multi-depth soil, SOIL1..4),
`EM500-CO2-915M-1..4` (CO₂, humidity, temperature, atmospheric pressure),
`EM500-PP-4842` (raw pressure proxy), and `SenseCAP-S2103-CO2-1..2` (CO₂).
Pulled with `vine.d1_pipeline.InfluxReader` (see
[ADR-0008](../adr/0008-sensor-source-influxdb.md)). A bounded 2026-07-23 pull
preserved 22,256 EM500-PP observations spanning 2026-01-22 through 2026-07-23.
The deployment KMZ contains its point at approximately 38.45562, −122.89878,
but its engineering unit, active direction, served block, and event semantics
remain unverified. It is not used as irrigation ground truth and does not unblock
D4.

Derived: NDVI, NDRE (computed in `vine.d1_pipeline.indices`); rolling stats, lags,
cumulative GDD (`vine.d1_pipeline.features`).

## Collection & processing
- Sensors transmit over LoRaWAN → ThingsBoard → InfluxDB (`bucket=ihv`); we read
  with Flux via `vine.d1_pipeline.InfluxReader`. Token is an NRP secret (env only).
- Drones capture multispectral orthomosaics, georeferenced to block geometry.
- Pipeline (`vine.d1_pipeline`): parse → resample to regular grid → flag gaps &
  out-of-range values → compute indices → align to blocks → engineer features.

## Known issues / quality
- **Gaps & noise:** sensor failures and connectivity drops. The pipeline flags
  gaps explicitly and never silently imputes (`vine.d1_pipeline.validation`).
- **Imagery cadence** depends on weather and flight scheduling.
- **Harvest labels are sparse** (≈1 per block per year), so multi-year history is
  essential; D4 may be scoped to exploratory analysis if insufficient.

## Reproducible profile

The mentor-requested offline D1 profile is available at
`notebooks/02_pipeline_datasheet.ipynb` in the repository. After `dvc pull`, it
profiles sensor gaps and cadence, weather/ET₀ coverage, all 39 block polygons
with deployed points, and the metadata-only imagery inventory without network
access.

## Storage & access
- Stored on NRP Ceph-backed volumes and versioned with DVC, not committed to
  git. Folders: `data/raw` → `data/interim` → `data/processed`.

## Open questions for mentor
- Exact sensor schema, units, and sampling interval?
- Orthomosaic band order, resolution, and CRS?
- How many seasons of historical harvest/irrigation records exist?
- What labeled imagery (stress/pest) is available for supervised CV?

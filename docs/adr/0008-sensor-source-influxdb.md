# ADR-0008: Sensor data comes from InfluxDB (ThingsBoard), not files

- **Status:** Accepted
- **Date:** 2026-05-25
- **Deciders:** Sohan Shingade (+ mentor)

## Context
The NRP starter repo
(`nrp-precision-agriculture/iron-horse-vineyards/jupyter-notebooks`) shows that
IHV sensors report over LoRaWAN into **ThingsBoard**, which writes to an
**InfluxDB** time-series database. The starter notebooks query it directly with
Flux. This is the live source of truth for sensor data — earlier assumptions
about CSV/JSON files were wrong.

```
InfluxDB: https://nrp-thingsboard-influxdb.nrp-nautilus.io/
org="Iron Horse Vineyards"  bucket="ihv"
devices: SE01-LS-{1..4} (soil), SE0X-LS-1 (multi-depth), EM500-CO2-915M-{1..4},
         SenseCAP-S2103-CO2-{1,2}
measurements: device_frmpayload_data_{conduct,temp,water}_SOIL, _co2,
              _humidity, _temperature, _pressure
```

## Decision
Ingest sensor data via **InfluxDB Flux queries** (`vine.d1_pipeline.InfluxReader`,
`influxdb-client`), pivoting `_measurement` into tidy time-indexed frames. The
token is read from `VINE_INFLUX_TOKEN` (an NRP secret) — **never hardcoded**.
Raw pulls are snapshotted to `data/raw/` and pinned with DVC for reproducibility.
NDP/CKAN ([ADR-0006](0006-ndp-data-access.md)) remains the channel for *published*
dataset exports; InfluxDB is the *live* source.

## Considered options
- **Query InfluxDB directly (chosen)** — matches how the data actually flows;
  always current; same path the starter notebooks use.
- **Only consume NDP exports** — simpler auth, but stale and dependent on someone
  exporting; not the live signal.
- **Hit ThingsBoard's REST API** — possible, but InfluxDB + Flux is the
  documented, demonstrated path and better for bulk time-series pulls.

## Consequences
- **Good:** live, reproducible sensor ingestion; clean separation of live source
  (InfluxDB) vs versioned snapshot (DVC) vs published export (NDP).
- **Bad:** requires a managed InfluxDB token (rotate-able secret); Flux/measurement
  names are deployment-specific and may change as sensors are added.
- ⚠️ **Security:** the starter repo commits a live InfluxDB token in plaintext.
  Flagged to the mentor for rotation; this project keeps the token in env/secrets
  only and never commits it.

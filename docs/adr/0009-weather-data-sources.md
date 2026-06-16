# ADR-0009: Weather data — reanalysis archive + forecast, not AWIPS for history

- **Status:** Accepted
- **Date:** 2026-06-16
- **Deciders:** Sohan Shingade (+ mentor)

## Context
The proposal needs weather both as a **historical archive** (features for irrigation
and harvest models: GDD, evapotranspiration, rainfall) and as a **forecast**
(irrigation must predict moisture *ahead*). On-site LoRaWAN sensors give local
point weather but are recent-only and gappy. `python-awips` was proposed.

`python-awips` queries an EDEX server, but EDEX retention is short (default ~1 day;
obs kept days, not years) — it is built for real-time + forecast, **not multi-year
historical archives**. So it's the wrong tool for the *historical* need.

## Decision
Split weather by need:

| Need | Source | Why |
|------|--------|-----|
| **Historical** | **Open-Meteo Archive API** (ERA5, 1940→now, free, no key) and/or **gridMET** (4 km daily CONUS, 1979→now, includes reference ET) | reanalysis covers the full period; gridded to vineyard coords (38.457, −122.896) so no station-distance error; gridMET already familiar from the Wildfire project |
| **Forecast** | Open-Meteo Forecast API (or `python-awips`) | short-horizon weather to drive irrigation lead time |

Confirmed working (2026-06-16): Open-Meteo archive returns daily tmax/tmin/precip
and `et0_fao_evapotranspiration` at the vineyard coordinates.

## Considered options
- **Open-Meteo / gridMET for history (chosen)** — long records, free, point/grid
  queries, ET included; no auth.
- **python-awips for history (rejected)** — EDEX retention too short to serve
  multi-year archives; better reserved for forecast/recent obs.
- **On-site sensors only** — local and authoritative but recent-only, gappy, and
  no forecast.

## Consequences
- **Good:** full historical weather + ET with no credentials; reproducible; covers
  the proposal's "weather archive + forecast" feature needs.
- **Bad:** reanalysis is gridded (~9–25 km ERA5 / 4 km gridMET), coarser than the
  on-site station — fine for GDD/ET trends, not micro-climate. Two sources to
  reconcile (sensor vs reanalysis). Adds a network dependency to the pipeline.

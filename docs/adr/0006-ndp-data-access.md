# ADR-0006: Access data via the National Data Platform (NDP)

- **Status:** Accepted (API confirmed 2026-06-16)
- **Date:** 2026-05-25 (updated 2026-06-16)
- **Deciders:** Sohan Shingade (+ mentor)

> ✅ **Confirmed (2026-06-16):** NDP's CKAN API lives under **`/catalog/`**:
> `https://nationaldataplatform.org/catalog/api/3/action/package_search` (public,
> no auth). The earlier `/api/3/...` 404 was the wrong path. NDP is a **catalog**
> (metadata only) — it does not host data, it *points to* it. The Iron Horse org
> has two datasets: `iot-sensor-data` → **InfluxDB** ([ADR-0008](0008-sensor-source-influxdb.md)),
> and `multispectral-drone-imagery` → **NextCloud files + a STAC catalog**
> (`ndp-test.sdsc.edu/stac`). So NDP is the **discovery layer** that tells us
> where each input lives; the bytes live in InfluxDB / NextCloud.
> `NDPClient` base URL must include `/catalog`.

## Context
One of VINE's stated goals is "open, shareable datasets for collaborative
research." The National Data Platform ([NDP](https://nationaldataplatform.org))
is a CKAN-based catalog and lists an Iron Horse Vineyards organization, so it is
the likely place cleaned data gets *published*. We want a reproducible way to
pull published datasets rather than hand-copying files — if/when they land there.

## Decision
Access NDP through its **CKAN Action API** via a small typed client
(`vine.d1_pipeline.ndp.NDPClient`). Base URL, org slug, and API key are configurable
(`VINE_NDP_*`). Raw pulls land in `data/raw/` and are then versioned with DVC
([ADR-0005](0005-experiment-tracking.md)) — NDP is the upstream source of truth,
DVC pins the exact snapshot we trained on.

## Considered options
- **CKAN API client (chosen)** — programmatic, scriptable, reproducible; same
  catalog the rest of the VINE org uses; works for search + download.
- **Manual download** — fast to start, but unreproducible and undocumented.
- **Direct DB/S3 access to the source** — bypasses the catalog's metadata,
  licensing, and versioning; couples us to infrastructure we don't own.

## Consequences
- **Good:** reproducible data provenance (NDP package id + DVC hash); easy to
  re-pull updated datasets; aligns with the project's open-data goal.
- **Bad:** the exact NDP API path + auth model must be **confirmed with the
  mentor** (defaults target the public catalog); some datasets may be embargoed
  and require an API key. The client wraps only the few CKAN actions we need.
```
NDP (CKAN) ──NDPClient──> data/raw/ ──dvc add──> S3 remote (versioned snapshot)
```

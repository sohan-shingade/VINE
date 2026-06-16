# VINE — Current State & Progress Tracker

> **Single source of truth for "where are we."** Git-tracked so it survives any
> session, machine, or context reset. **Any new session: read this first.**
> Update it at the end of any session that changes status. Last updated:
> **2026-06-16**. Phase: **Community Bonding** (understanding inputs).

## TL;DR — resume here

The repo scaffold, Claude Code setup, and wiki are built. We are in the
**understand-the-data** phase of D1. **Three of four data inputs are located and
verified reachable; the pipeline itself is NOT built yet** (deliberately — we're
scoping first). Next real work: confirm open questions with mentor, then build D1
ingestion on the confirmed sources.

## Verified facts & live endpoints

Everything here has been **tested and confirmed working** from this machine
(secrets live in `.env`, gitignored — never commit them).

| Resource | Endpoint | Access | Verified |
|----------|----------|--------|----------|
| Sensors (InfluxDB) | `https://nrp-thingsboard-influxdb.nrp-nautilus.io` org `Iron Horse Vineyards`, bucket `ihv` | Flux + `VINE_INFLUX_TOKEN` | ✅ pulled 7,615 rows; `vine ingest` works |
| NRP S3 (Pool West) | `https://s3-west.nrp-nautilus.io`, bucket `ihv-vine` | `AWS_ACCESS_KEY_ID/SECRET` in `.env` | ✅ created bucket, read/write round-trip |
| DVC remote | `s3://ihv-vine/dvc` on NRP S3 | configured `.dvc/config` + creds `.dvc/config.local` | ✅ pushed sensor snapshots |
| NDP catalog API | `https://nationaldataplatform.org/catalog/api/3/action/` | public, no auth | ✅ found the 2 IHV datasets |
| Imagery STAC | `https://ndp-test.sdsc.edu/stac/collections/IHV_DJI_MULTISPECTRAL_DCIM` | public | ✅ inventoried 9,295 captures |
| Imagery files | `https://nextcloud.nrp-nautilus.io/s/ieAqEKDDKeYq9q4` | public share | ⛔ HTTP 503 maintenance (retry later) |
| Weather (historical) | `https://archive-api.open-meteo.com/v1/archive` | public, no key | ✅ daily tmax/tmin/precip/ET₀ at vineyard coords |
| NRP managed LLM | `https://ellm.nrp-nautilus.io/v1` | `VINE_NRP_LLM_API_KEY` in `.env` | ✅ lists 11 models |
| Kubernetes (`ihv` ns) | Nautilus cluster | kubeconfig (not yet obtained) | ⬜ not set up — only needed to run jobs *on* NRP |

Vineyard location: **38.457 N, −122.896 W** (Sebastopol, CA). Blocks seen in
imagery: `Cd, H5, H4, E, H2, Q, Ce`.

## The 4 data inputs (D1)

| # | Input | Source (confirmed) | How to get it | Status |
|---|-------|--------------------|---------------|--------|
| 1 | Sensors | InfluxDB bucket `ihv` | `vine.d1_pipeline.InfluxReader` (Flux) | ✅ working |
| 2 | Drone imagery | NextCloud files + STAC index | STAC API now; NextCloud download when up | ✅ scoped, files behind maintenance |
| 3 | Historical harvest/yield/irrigation | **NOT in InfluxDB or NDP** — vineyard/mentor | TBD | ⚠️ ask mentor; only D4 needs it |
| 4 | Weather (hist + forecast) | Open-Meteo / gridMET (hist), Open-Meteo / python-awips (forecast) | Open-Meteo archive API ✅ | ✅ source confirmed |

**Imagery inventory (from STAC, 2026-06-16):** 9,295 capture points, 11 flights
(2025-08-27 → 2026-01-08), DJI Mavic 3 Multispectral. Each capture: `visual` (RGB)
+ `green/red/rededge/nir` (TIF, ~7,868 with full multispectral). Raw per-photo, NOT
stitched → D1 must stitch/orthomosaic + align to blocks. Flight timing skews to
winter/dormant; the useful growing-season flights are Aug (pre-harvest) + Oct
(harvest) — few of them.

## Deliverable progress

`☐ todo · ◐ in progress · ☑ done`

| D | Deliverable | Status | Notes |
|---|-------------|--------|-------|
| — | Repo + Claude Code scaffold + wiki | ☑ | builds green: ruff/mypy/17 tests |
| D1 | Data pipeline | ◐ | inputs scoped + sensor ingestion working; imagery/weather/historical not built |
| D2 | Irrigation models | ☐ | |
| D3 | Plant-health CV | ☐ | |
| D4 | Harvest timing | ☐ | depends on input #3; descopable to exploratory |
| D5 | Evaluation report | ☐ | |
| D6 | NRP deployment | ☐ | needs kubectl/kubeconfig |
| D7 | Docs + devlog | ◐ | wiki live; devlog started |

## Done log

- **2026-06-16** — Scaffolded repo (`src/vine`, tests, configs, docker, k8s),
  Claude Code setup (CLAUDE.md, commands, agents, hook), MkDocs wiki, 9 ADRs.
- **2026-06-16** — Verified InfluxDB; built + ran `vine ingest` (9 devices).
- **2026-06-16** — Verified NRP S3, wired DVC remote, pushed sensor snapshots.
- **2026-06-16** — Found NDP catalog API (`/catalog/...`); located imagery (STAC)
  + sensors; inventoried 9,295 imagery captures.
- **2026-06-16** — Confirmed Open-Meteo historical weather + ET₀. Recorded
  weather decision (ADR-0009).

## Open questions for mentor

1. **Historical records** (harvest dates, yields, irrigation logs) — do they exist,
   and where? Not in InfluxDB or NDP. (Drives D4 scope.)
2. **Imagery** — when will NextCloud be back? Are stitched orthomosaics available,
   or do we stitch the raw M3M photos ourselves? More growing-season flights coming?
3. **Labeled imagery** for plant stress/pest (D3) — does any exist?
4. **NRP access** — sponsor my kubeconfig for namespace `ihv`; confirm storage
   classes + GPU reservation process.
5. **Security** — the InfluxDB token is committed in the public starter repo; rotate?

## Next actions (when resuming)

1. Get the open questions answered by mentor.
2. (No-blocker) Build D1 sensor path properly: regularize → gap-flag → features.
3. Add a thin Open-Meteo weather reader (input #4) — confirmed working.
4. Set up kubeconfig to run ingestion as the `ihv` CronJob (optional until scaling).

## How we keep state across sessions

- **This file (`docs/STATE.md`)** is the durable handoff — update it, commit it.
- **`CLAUDE.md`** points new sessions here and stays lean (loaded every session).
- **Decisions** → ADRs in `docs/adr/`. **Narrative** → `docs/devlog/`.
- Secrets stay in `.env` (gitignored); this file references them, never contains them.

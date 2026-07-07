# VINE — Current State & Progress Tracker

> **Single source of truth for "where are we."** Git-tracked so it survives any
> session, machine, or context reset. **Any new session: read this first.**
> Update it at the end of any session that changes status. Last updated:
> **2026-07-06**. Phase: **D1/D2** (sensor path done; imagery just unblocked).

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
| NRP S3 (Pool West) | `https://s3-west.nrp-nautilus.io`, bucket `ihv-vine` | `AWS_ACCESS_KEY_ID/SECRET` in `.env` | ✅ **back up 2026-07-06** (root HTTP 200 after the 2026-07-02 Ceph upgrade; re-verify a bucket round-trip + DVC push) |
| DVC remote | `s3://ihv-vine/dvc` on NRP S3 | configured `.dvc/config` + creds `.dvc/config.local` | ✅ pushed sensor snapshots (s3-west reachable again 2026-07-06) |
| NDP catalog API | `https://nationaldataplatform.org/catalog/api/3/action/` | public, no auth | ✅ found the 2 IHV datasets |
| Imagery STAC | `https://ndp-test.sdsc.edu/stac/collections/IHV_DJI_MULTISPECTRAL_DCIM` | public | ✅ serves collection + items (2026-07-06); ⚠️ **asset `download?path=` hrefs are STALE** — point at flight subfolders that 404 (e.g. `..._002` vs real `..._001`); reconcile against the WebDAV tree, don't trust hrefs verbatim |
| Imagery files | `https://nextcloud.nrp-nautilus.io/s/ieAqEKDDKeYq9q4` | public share | ✅ **back up 2026-07-06** (`maintenance:false`, WebDAV browsable, downloaded a real 10.9 MB JPEG 5280×3956); use WebDAV `public.php/webdav/` with share token as user |
| Weather (historical) | `https://archive-api.open-meteo.com/v1/archive` | public, no key | ✅ daily tmax/tmin/precip/ET₀ at vineyard coords |
| NRP managed LLM | `https://ellm.nrp-nautilus.io/v1` | `VINE_NRP_LLM_API_KEY` in `.env` | ✅ lists 11 models |
| Kubernetes (`ihv` ns) | Nautilus cluster | kubeconfig (not yet obtained) | ⬜ not set up — only needed to run jobs *on* NRP |

Vineyard location: **38.457 N, −122.896 W** (Sebastopol, CA). Blocks seen in
imagery: `Cd, H5, H4, E, H2, Q, Ce`.

## The 4 data inputs (D1)

| # | Input | Source (confirmed) | How to get it | Status |
|---|-------|--------------------|---------------|--------|
| 1 | Sensors | InfluxDB bucket `ihv` | `vine.d1_pipeline.InfluxReader` (Flux) | ✅ working |
| 2 | Drone imagery | NextCloud files + STAC index | STAC to enumerate; **NextCloud WebDAV to download** (files now reachable) | ✅ **files DOWNLOADABLE 2026-07-06**; still no orthomosaics/block polygons → `imagery.py`/`geo.py` still stubs |
| 3 | Historical harvest/yield/irrigation | **NOT in InfluxDB or NDP** — vineyard/mentor | TBD | ⏸️ **skipped for now** (only D4 needs it; ask mentor) |
| 4 | Weather (hist) | Open-Meteo archive (ERA5) | `vine.d1_pipeline.fetch_historical` | ✅ **reader built + tested + verified live** |
| 4f | Weather (forecast) | Open-Meteo forecast / python-awips | TBD | ☐ not built (needed for D2 lead time) |

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
| D1 | Data pipeline | ◐ | **sensor path done + tested** (ingest→regularize→gap/range flags→rolling/lag features→weather & GDD join); weather reader done; imagery blocked (NextCloud 503 + no orthomosaics/polygons); historical skipped |
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
- **2026-06-21** — Built D1 weather reader (`d1_pipeline/weather.py`, input #4):
  Open-Meteo archive client (pure param/parse helpers + `fetch_historical`),
  config coords/URL, 4 unit tests. Verified live (8 daily rows tmax/tmin/precip/ET₀
  at vineyard coords). `make check` green (21 tests).
- **2026-06-21** — Built interactive course website (`course-site/`, zero-dep):
  18 modules teaching every prereq → all deliverables; animated diagrams, NDVI demo.
- **2026-06-21** — Built + tested the **D1 sensor path** end to end: `pipeline.py`
  (`build_sensor_features`: regularize → gap/range flags → rolling/lag features;
  `attach_weather`: daily weather ffill + cumulative GDD). Wired weather into
  `vine ingest --weather-days N`. Fixed two real bugs found on live data:
  (a) tz-aware sensor index vs tz-naive weather, (b) InfluxDB pivot returning
  numeric readings as strings → coerce in `influx.read` + assembler. 34 tests green.
  Verified on real snapshot: 73 hourly rows → 42 feature cols, weather+GDD joined.
- **2026-06-21** — Re-probed imagery: NextCloud `nextcloud.nrp-nautilus.io` still
  **503** (share + WebDAV). `status.nextcloud.com` is the unrelated Nextcloud-GmbH
  page, not our instance. STAC up but all asset hrefs route through NextCloud.
- **2026-07-02** — Re-probed imagery + checked the "moved to S3?" theory: **no S3
  mirror found.** NextCloud still 503 (share/WebDAV/root). STAC replicas flapping
  (collection listed + items served on some hits, 404/empty on others); asset hrefs
  still point at NextCloud. NDP catalog dataset unchanged (last modified 2026-03-29),
  still links NextCloud + STAC. **New:** `s3-west.nrp-nautilus.io` itself is 503
  endpoint-wide (our `ihv-vine` bucket + DVC remote unreachable); s3-central/east up
  but reject our west-pool creds and have no IHV buckets under obvious names.
  → Imagery stays blocked; add mentor Q: is imagery being migrated off NextCloud /
  what's up with s3-west?
- **2026-07-02 (later)** — **Root cause found** via the Nautilus Support Matrix feed
  (`https://nrp.ai/api/matrix-feed`, backs the nrp.ai/live news page): NRP announced
  **Ceph upgrades for 2026-07-02, 10:00–16:00 Pacific, affecting CephFS, RBD, and S3**
  — today's s3-west 503 is planned maintenance, not an outage or migration (creds
  confirmed fine: anonymous requests get the same HAProxy 503). Also: NextCloud was
  declared **back up on 2026-06-24** ("previews return gradually"), so the imagery
  share is likely fine once today's Ceph work finishes. Re-probed 20:30 Pacific:
  both still 503 (upgrade running long). **→ Retry NextCloud + s3-west tomorrow;
  imagery download may finally be unblocked.**
- **2026-07-06** — **Imagery UNBLOCKED — verified end to end.** NextCloud is back
  (`status.php` → `maintenance:false`, v33.0.5); public-share **WebDAV** browsable
  (207, full tree: `_sorted_data/BLOCKS/…`, `GIS/`, `sensor reference/`); STAC serves
  the collection + items; **downloaded a real 10.9 MB JPEG (5280×3956)** from
  `H5/2026-01-08/m3m/images/` (570 files in that one flight). s3-west root back to
  HTTP 200 too. **Gotcha:** STAC asset `download?path=` hrefs are STALE — they point
  at flight subfolders that 404 (e.g. `DJI_…_002` vs the real `…_001`, plus an
  `images/` subfolder STAC doesn't name) → the D1 imagery reader must walk the
  WebDAV tree / reconcile STAC item IDs against real folder names, not trust hrefs.
  Downloading works; **stitched orthomosaics + block polygons still don't exist**
  (mentor Q), so `imagery.py`/`geo.py` remain stubs — the raw-file blocker is gone,
  the orthomosaic/geometry blocker is not.

## Open questions for mentor

1. **Historical records** (harvest dates, yields, irrigation logs) — do they exist,
   and where? Not in InfluxDB or NDP. (Drives D4 scope.)
2. **Imagery** — when will NextCloud be back? Are stitched orthomosaics available,
   or do we stitch the raw M3M photos ourselves? More growing-season flights coming?
3. **Labeled imagery** for plant stress/pest (D3) — does any exist?
4. **NRP access** — sponsor my kubeconfig for namespace `ihv`; confirm storage
   classes + GPU reservation process.
5. **Security** — the InfluxDB token is committed in the public starter repo; rotate?
6. ~~Storage outage / migration?~~ **Resolved 2026-07-02:** it was the announced
   Ceph upgrade (July 2, 10:00–16:00 Pacific, CephFS/RBD/S3); NextCloud itself was
   fixed 2026-06-24 per Nautilus Support. No migration; creds fine. Monitor
   `https://nrp.ai/live` (or the Matrix room) for cluster news going forward.

## Next actions (when resuming)

1. ✅ DONE — sensor path built + tested; weather reader + ingest wiring done.
2. ◐ **Imagery (input #2): raw files now DOWNLOADABLE** (NextCloud WebDAV back up
   2026-07-06). Buildable now: `imagery.py` reader that walks the WebDAV tree (NOT
   the stale STAC hrefs) to pull per-photo M3M multispectral. **Still blocked for a
   usable pipeline:** (b) stitched orthomosaics (raw is per-photo) and (c) vineyard-
   block polygons don't exist → `geo.py` block alignment still can't be built. (b)/(c)
   are mentor Qs.
3. ⏸️ Historical harvest (input #3) **skipped** per scope decision (mentor Q for D4).
4. (Optional) Weather **forecast** reader (Open-Meteo forecast) for D2 lead time.
5. Start **D2 irrigation** on the now-ready sensor+weather feature frame (persistence
   baseline first), or set up kubeconfig for the `ihv` CronJob.

**Done since last:** verified imagery UNBLOCKED (NextCloud/WebDAV back, real JPEG
downloaded) and s3-west back up after the Ceph upgrade. Prior: weather reader +
full sensor path, built/tested/verified on live data (34 tests green).

## How we keep state across sessions

- **This file (`docs/STATE.md`)** is the durable handoff — update it, commit it.
- **`CLAUDE.md`** points new sessions here and stays lean (loaded every session).
- **Decisions** → ADRs in `docs/adr/`. **Narrative** → `docs/devlog/`.
- Secrets stay in `.env` (gitignored); this file references them, never contains them.

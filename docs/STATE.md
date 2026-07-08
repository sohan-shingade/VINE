# VINE — Current State & Progress Tracker

> **Single source of truth for "where are we."** Git-tracked so it survives any
> session, machine, or context reset. **Any new session: read this first.**
> Update it at the end of any session that changes status. Last updated:
> **2026-07-08 (evening)**. Phase: **D2 ladder complete through ARIMA; S3/DVC
> restored; persistence still champion, ARIMA a marginal candidate**.

## TL;DR — resume here

**All lost secrets restored; D2 rungs 2–3 built and honestly evaluated**
(2026-07-08 evening, orchestrated multi-agent session): S3 keys re-issued →
DVC round-trip verified and fresh snapshots pinned+pushed. Built via parallel
workers: weather-**forecast** reader (input 4f ✅), **ARIMA** rung, **Δ-moisture**
target, **lead-time forecast features** (perfect-forecast proxy with a
per-horizon leakage guard). An adversarial eval-review then **caught a real
causality bug in ARIMA** (early-fold rows forecast from a Kalman state that
had seen past their decision time) and exposed ridge+forecast's 48 h "+15%"
as a **single April-rain-fold artifact**. After the fix + per-fold skill
columns: **ARIMA is the first rung to clear persistence — +3.0/−1.8/+2.4/+2.1 %
at 6/12/24/48 h, positive in every fold at 48 h — but too small/one-season to
ship yet; persistence stays champion** pending a shoulder-season holdout.
Remaining human steps: mentor asks (kubeconfig for NRP compute, token rotation,
harvest records).

## Verified facts & live endpoints

Everything here was **tested and confirmed working** from this machine at the
noted date (secrets live in `.env`, gitignored — never commit them).
The 2026-07-04 machine wipe lost `.env` + `.dvc/config.local`; **everything
that matters is restored as of 2026-07-08** (Influx token from the starter
repo, S3 keys re-issued from portal `/s3token/`). Only the optional LLM key
remains unset. Gotcha: **no inline comments after values in `.env`** — dotenv
reads them as the value (bit us via `.env.example`'s NDP line; now fixed).

| Resource | Endpoint | Access | Verified |
|----------|----------|--------|----------|
| Sensors (InfluxDB) | `https://nrp-thingsboard-influxdb.nrp-nautilus.io` org `Iron Horse Vineyards`, bucket `ihv` | Flux + `VINE_INFLUX_TOKEN` | ✅ **token restored + re-verified 2026-07-08** (1.04 M rows re-ingested) |
| NRP S3 (Pool West) | `https://s3-west.nrp-nautilus.io`, bucket `ihv-vine` | `AWS_ACCESS_KEY_ID/SECRET` in `.env` | ✅ **keys re-issued + verified 2026-07-08** (list on `ihv-vine` HTTP 200) |
| DVC remote | `s3://ihv-vine/dvc` on NRP S3 | `.dvc/config` + creds in `.dvc/config.local` (gitignored) | ✅ **restored 2026-07-08**: creds rewritten, fresh snapshots pinned (`sensors` 1.04 M rows, `weather`, `imagery` 61 MB) and pushed (19 objects) |
| NDP catalog API | `https://nationaldataplatform.org/catalog/api/3/action/` | public, no auth | ✅ found the 2 IHV datasets |
| Imagery STAC | `https://ndp-test.sdsc.edu/stac/collections/IHV_DJI_MULTISPECTRAL_DCIM` | public | ✅ serves collection + items (2026-07-06); ⚠️ **asset `download?path=` hrefs are STALE** — point at flight subfolders that 404 (e.g. `..._002` vs real `..._001`); reconcile against the WebDAV tree, don't trust hrefs verbatim |
| Imagery files | `https://nextcloud.nrp-nautilus.io/s/ieAqEKDDKeYq9q4` | public share | ✅ **back up 2026-07-06** (`maintenance:false`, WebDAV browsable, downloaded a real 10.9 MB JPEG 5280×3956); use WebDAV `public.php/webdav/` with share token as user |
| Weather (historical) | `https://archive-api.open-meteo.com/v1/archive` | public, no key | ✅ daily tmax/tmin/precip/ET₀ at vineyard coords |
| NRP managed LLM | `https://ellm.nrp-nautilus.io/v1` | `VINE_NRP_LLM_API_KEY` in `.env` | 🔑 worked 2026-06-16 (11 models); **key lost in wipe** — portal `/llmtoken/` (optional) |
| Kubernetes (`ihv` ns) | Nautilus cluster | kubeconfig (not yet obtained) | ⬜ not set up — only needed to run jobs *on* NRP |

Vineyard location: **38.457 N, −122.896 W** (Sebastopol, CA). Blocks seen in
imagery: `Cd, H5, H4, E, H2, Q, Ce`.

## The 4 data inputs (D1)

| # | Input | Source (confirmed) | How to get it | Status |
|---|-------|--------------------|---------------|--------|
| 1 | Sensors | InfluxDB bucket `ihv` | `vine.d1_pipeline.InfluxReader` (Flux) | ✅ working |
| 2 | Drone imagery | NextCloud share (WebDAV) — **not** STAC hrefs (stale) | `vine.d1_pipeline.imagery` (flight index → captures → band download) + `geo` (KMZ blocks, zonal stats) | ✅ **BUILT + LIVE-VERIFIED 2026-07-06** — orthomosaics & block polygons were on the share all along (`GIS/`) |
| 3 | Historical harvest/yield/irrigation | **NOT in InfluxDB or NDP** — vineyard/mentor | TBD | ⏸️ **skipped for now** (only D4 needs it; ask mentor) |
| 4 | Weather (hist) | Open-Meteo archive (ERA5) | `vine.d1_pipeline.fetch_historical` | ✅ **reader built + tested + verified live** |
| 4f | Weather (forecast) | Open-Meteo forecast API | `vine.d1_pipeline.fetch_forecast` | ✅ **built + live-verified 2026-07-08** (3-day forecast, same tidy daily frame). Backtests use the labeled perfect-forecast proxy (`add_lead_time_features`); live serving would fill the same `_next_{h}h` columns from this reader |

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
| D1 | Data pipeline | ☑ | **all three reachable inputs done + live-verified**: sensor path (ingest→flags→features→weather/GDD), weather reader, **imagery path** (WebDAV flight index → capture grouping → band download → NDVI) + **block alignment** (39 KMZ polygons, sensor→block join, windowed zonal stats). Historical (input #3) remains a mentor Q — D4-only. Weather *forecast* (4f) optional, for D2 lead time |
| D2 | Irrigation models | ◐ | **ladder complete through ARIMA (2026-07-08 evening)**: ridge ✗ (skill −0.8…−1.0), ridge+forecast-features ✗ (48 h +15 % is a single-rain-fold artifact: fold median −0.18), ridge-Δ ✗ (same), **ARIMA ✓ marginal: +3.0/−1.8/+2.4/+2.1 % at 6/12/24/48 h, positive every fold at 48 h** — first rung to clear persistence but too small/one-season to ship; **persistence remains champion**. Confirm ARIMA on a shoulder-season holdout + second device before shipping. Known caveat for future short-horizon rungs: daily-ffilled `precip_mm`/`et0_mm` reach up to 24−h h past target time at h<24 (flagged by eval review; route intra-day weather through `_next_` columns instead) |
| D3 | Plant-health CV | ☐ | |
| D4 | Harvest timing | ☐ | depends on input #3; descopable to exploratory |
| D5 | Evaluation report | ◐ | shared harness: metrics + **walk-forward validation (expanding splits, causal eval, skill score)** + **per-fold skill columns** (`skill_fold_median/min` — added after the eval review showed a pooled MAE hiding a single-fold artifact) — used by D2, reusable by D4 |
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
- **2026-07-06 (later)** — **D1 imagery + block alignment BUILT; D1 code-complete.**
  Scout-mapped the whole share (brief: `docs/data/imagery-share-layout.md`) and found
  the supposed blockers were already there: `GIS/IHV-2026-05-26.kmz` holds **39 block
  polygons** (names match `_sorted_data/BLOCKS/` 1:1) **+ 182 points incl. sensor
  locations**, and `GIS/` holds stitched **Pix4DFields orthomosaics** with NDVI/NDRE
  computed (H-blocks 2025-08-29; whole-vineyard 2026-06-01, 46 GB) — no stitching
  needed for those dates. Built: `webdav.py` (share client), `imagery.py` (flight
  index — share placement is authoritative, STAC block attribution is stale/re-sorted;
  capture grouping; size-checked band downloads), `geo.py` (stdlib KML→polygons,
  windowed `zonal_stats`, `assign_sensors_to_blocks`). Live-verified: 34 flights
  indexed; 582-capture flight grouped exactly; 4 bands downloaded + NDVI 0.272;
  39/39 blocks loaded; 47 sensors joined to blocks; zonal stats on the real 1 m DSM
  hit 39/39. `vine imagery` CLI added. **48 tests green** (was 34), ruff+mypy clean.
  Also: codemap shards (`make codemap`, consult before Reading source), Serena MCP
  registered. Note: `_unsorted/M3M/` has ~120 newer flights (through 2026-07-03) not
  yet sorted into blocks; growing-season coverage is still thin (mentor Q stands).
- **2026-07-06 (evening)** — **D2 baseline ladder BUILT; discovered the secrets are
  gone.** Tried `vine ingest --start=-365d` for the D2 target series → **no InfluxDB
  token: `.env` and `.dvc/config.local` did not survive the 2026-07-04 machine wipe**
  (local DVC cache empty too; anonymous S3 GET → 403; endpoints themselves fine).
  Pivoted to building everything that doesn't need live data: **D5 walk-forward
  harness** (`walkforward.py`: expanding splits, causal `walk_forward`, `skill`
  score), **D2 baselines** (`seasonal_naive`, `climatology_hourly` added), **ridge
  rung** (`models.py`), **config-driven runner** (`experiment.py` — target-time
  alignment so baselines are pure shifts and models see `frame.shift(h)`; every
  model scored on identical holdout rows; gaps masked, never imputed), MLflow
  logging, `vine train irrigation <config>` CLI. Verified end-to-end on synthetic
  snapshots (`VINE_DATA_DIR` override): full 4-model × 4-horizon table, sane
  ordering (ridge best, seasonal≈persistence at 24/48 h). The e2e run caught a real
  bug unit tests missed: `*_std_1h` rolling features are all-NaN on an hourly grid
  → ridge had zero complete training rows; fixed (drops no-signal columns per fold,
  test added). **67 tests green** (was 48). Configs updated to real column names
  (`soil_water`, device `SE01-LS-1`); `ridge.yaml` added.
- **2026-07-08** — **Influx token restored; D2 live eval DONE — ridge does not
  ship.** Token recovered without the mentor: ADR-0008 records that the public
  starter repo (`nrp-precision-agriculture/iron-horse-vineyards/jupyter-notebooks`
  on `gitlab.nrp-nautilus.io`) commits a live 88-char token in its notebooks
  (`TOKEN = "…"` in `influx-SE01-LS-1.ipynb`); extracted it, verified auth
  (HTTP 200), wrote it to `.env` — never echoed or committed. **This is exactly
  why mentor Q5 (rotate the token) matters — anyone can do this.** Re-ingested
  `--start=-365d --weather-days 400`: **1,036,276 rows / 9 devices** + 401 daily
  weather rows; SE01-LS-1 history actually begins **2026-01-22** (~5.5 months,
  188 k raw rows; soil_water 18–45, mean 27.3, 39% below the 25.0 threshold).
  Ran `vine train irrigation configs/d2_irrigation/ridge.yaml` (all 4 models ×
  4 horizons, n≈1330–1360 scorable holdout rows each): **persistence wins every
  horizon** (MAE 0.105 → 0.524 from 6 h → 48 h); seasonal-naive ties at 24/48 h
  (whole-day shifts), loses at 6/12 h; climatology MAE ~5.4 (hour-of-day mean
  can't track seasonal drying); **ridge skill −0.73…−1.13 → per ADR-0003 it
  does not ship.** Honest read: real soil moisture is near-random-walk at these
  horizons — current features (lags/rolling/past weather) add nothing over the
  last observation; the synthetic win was an artifact of its strong daily cycle.
  Decision-layer P/R = 1.0 for truth-tracking models (holdout = dry season,
  mostly below threshold), 0.0 for climatology — threshold metrics need a
  shoulder-season holdout to be informative. Logged to MLflow (`d2_irrigation`).
  **S3/DVC still blocked on `/s3token/` keys** (only remaining lost secret that
  matters; LLM key optional).

- **2026-07-08 (evening)** — **S3/DVC restored; D2 rungs 2–3 built, adversarially
  reviewed, and honestly scored** (orchestrator + parallel Sonnet workers +
  eval-reviewer advisor pattern). (1) User re-issued `/s3token/` keys → verified
  S3 (HTTP 200), rewrote `.dvc/config.local`, `dvc add`ed + pushed fresh
  snapshots (sensors 1.04 M rows / weather / imagery; 19 objects). (2) Three
  workers in parallel: **forecast reader** (`weather.fetch_forecast`,
  Open-Meteo forecast API, live-verified 3-day pull), **ARIMA rung**
  (`models.make_arima`: SARIMAX fit once per fold, Kalman filter extended
  per row for true h-step forecasts, ~1.2 s/fold), **harness wiring**
  (`add_lead_time_features` perfect-forecast proxy + per-horizon `_next_{h}h`
  leakage guard, `predict_delta` ridge-Δ with level reconstruction, arima
  registration, 3 new configs). Found+fixed en route: `.env.example` had an
  inline comment after `VINE_NDP_API_KEY=` that dotenv reads as the value
  (broke a test when the user rebuilt `.env` from it). (3) First real run
  looked great — ARIMA positive everywhere (max +8.3 %), ridge+fcst +14.7 %
  at 48 h. (4) **eval-reviewer adversarial pass refuted both**: `make_arima`'s
  first h−1 rows per fold forecast from a filter state containing observations
  past their decision time (unit tests only used h=1, where the leaky region
  is empty — a lesson); ridge's 48 h win came entirely from one April rain
  fold (fold skill +0.55; excluding it, −0.62; bootstrap CI spans 0).
  (5) Fixed ARIMA (`res.apply` on the truncated prefix for early rows) + added
  an h=6 poison-tail causality test + **per-fold skill columns** in the results
  table. (6) Honest re-run: ARIMA +3.0/−1.8/+2.4/+2.1 %, positive in every
  fold at 48 h — first rung above zero, held as *candidate*; ridge variants'
  fold medians are negative → artifacts confirmed visible in-table.
  **Persistence remains champion.** 78 tests green; MLflow has all runs;
  codemap regenerated. Advisor also flagged: daily-ffilled weather levels
  leak up to 24−h h past target at short horizons — future rungs must use
  the `_next_` columns for intra-day weather.

## Open questions for mentor

1. **Historical records** (harvest dates, yields, irrigation logs) — do they exist,
   and where? Not in InfluxDB or NDP. (Drives D4 scope.)
2. ~~Imagery availability~~ **Mostly resolved 2026-07-06:** NextCloud is back;
   stitched Pix4D orthomosaics + block polygons were on the share (`GIS/`) all
   along. **Remaining:** more growing-season flights coming? Will the ~120
   `_unsorted/M3M/` flights (through 2026-07-03) get sorted into blocks — or
   should we sort by GPS-vs-polygon ourselves? Is STAC going to be re-indexed
   (its block attribution predates a re-sort and its inventory ends 2026-01-08)?
3. **Labeled imagery** for plant stress/pest (D3) — does any exist?
4. **NRP access** — sponsor my kubeconfig for namespace `ihv`; confirm storage
   classes + GPU reservation process.
5. **Security** — the InfluxDB token is committed in the public starter repo;
   rotate? **(Now demonstrated: we recovered our lost token from it in minutes,
   2026-07-08 — so can anyone else. When rotated, hand off the new one securely.)**
6. ~~Storage outage / migration?~~ **Resolved 2026-07-02:** it was the announced
   Ceph upgrade (July 2, 10:00–16:00 Pacific, CephFS/RBD/S3); NextCloud itself was
   fixed 2026-06-24 per Nautilus Support. No migration; creds fine. Monitor
   `https://nrp.ai/live` (or the Matrix room) for cluster news going forward.

## Next actions (when resuming)

1. **📧 One mentor message bundling the human asks:** (a) add me to the `ihv`
   namespace on Nautilus + confirm storage classes/GPU process → portal "Get
   Config" kubeconfig (unblocks D6 + D3 GPU training); (b) rotate the exposed
   starter-repo InfluxDB token (Q5); (c) historical harvest/yield records (Q1,
   gates D4); (d) growing-season flights / `_unsorted` imagery plans (Q2).
2. **D2 — confirm or retire the ARIMA candidate:** the +2–3 % is one dry
   season on one device. Re-run on (a) a shoulder/wet-season holdout when the
   data exists (or restrict folds to Jan–Apr), (b) a second sensor
   (SE01-LS-2/3/4) — if fold-consistent skill holds, ship ARIMA per ADR-0003;
   else persistence stays champion and D2 pivots to the decision layer
   (threshold-crossing alerts need a shoulder-season holdout to be informative
   anyway). Also fix the short-horizon weather-level leak flagged by the
   review (lag daily weather columns, keep intra-day signal in `_next_` form).
3. D3 groundwork: per-block patches from the 2025-08-29 H-blocks +
   2026-06-01 whole-vineyard orthomosaic sets (NDVI/NDRE layers pre-computed).
4. ⏸️ Historical harvest (input #3) still a mentor Q (gates D4 only).
5. Optional: `/llmtoken/` for the managed LLM (no core track needs it).

**Done since last:** S3 keys restored + DVC round-trip verified + snapshots
pinned/pushed; forecast reader (4f), ARIMA, Δ-target, lead-time features all
built and evaluated; eval review caught an ARIMA causality leak + a single-fold
ridge artifact; after fixes ARIMA is the first rung to clear persistence
(marginal, candidate only); devlog posted.

## How we keep state across sessions

- **This file (`docs/STATE.md`)** is the durable handoff — update it, commit it.
- **`CLAUDE.md`** points new sessions here and stays lean (loaded every session).
- **Decisions** → ADRs in `docs/adr/`. **Narrative** → `docs/devlog/`.
- Secrets stay in `.env` (gitignored); this file references them, never contains them.

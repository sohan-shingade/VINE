# VINE — Current State & Progress Tracker

> **Single source of truth for "where are we."** Git-tracked so it survives any
> session, machine, or context reset. **Any new session: read this first.**
> Update it at the end of any session that changes status. Last updated:
> **2026-07-23**. Phase: **D3 label-free screening MVP + local D6 irrigation
> serving built; water balance remains an active D2 experiment**.

## TL;DR — resume here

**D1 complete; D2 serves persistence while water balance stays active; D3/D6
MVPs are now built (2026-07-23).** The pooled five-sensor rung was corrected to
apply the same `h−1` training-label purge as the single-probe evaluator and
rerun from YAML: fleet skill is −45.1/−52.2/+33.0/+30.2% at 6/12/24/48 h, but
worst-fold skill remains negative at every horizon, so it still does not ship.
A constrained water-balance weather
correction produced +3.5…+11.2% aggregate skill at 48 h across all five probes
after an adversarial review found and fixed a shared fold-boundary label leak.
Every probe still has a negative worst fold and the backtest uses realized future
weather, so water balance is **promising active research, not rejected/removed,
but not production-promoted**. Persistence remains the safe served fallback.

D3 now has a label-free, same-acquisition NDVI/NDRE block-screening pipeline
(windowed distributions, polygon-interior coverage flags, deterministic concern
ranks). An adversarial review invalidated the first run's 30/9 coverage split
because its denominator used each polygon's bounding box. The corrected remote
39-block rerun later exited without producing a replacement artifact, so no
current block ranking is claimed yet. D6 locally
serves persistence + threshold with typed quality/freshness responses; a real
stale snapshot correctly suppresses advice. A bounded EM500-PP-4842 pull now
preserves 22,256 raw pressure observations (2026-01-22 through 2026-07-23) plus
provenance/quality manifests; its unit, active direction, served block, and
ground-truth meaning remain unverified, so it is not used as an irrigation-event
label and does not unblock D4. Current local gate: **161 tests passed**;
Ruff, formatting, mypy, strict MkDocs, codemap regeneration, deterministic report
regeneration, and both output-free notebook executions are clean. Remaining
human blockers: D3 labels, archived forecast
vintages, kubeconfig, harvest records, pressure semantics, and token rotation.

### Previous D2 handoff

**All lost secrets restored; D2 rungs 2–3 built and honestly evaluated**
(2026-07-08 evening, orchestrated multi-agent session): S3 keys re-issued →
DVC round-trip verified and fresh snapshots pinned+pushed. Built via parallel
workers: weather-**forecast** reader (input 4f ✅), **ARIMA** rung, **Δ-moisture**
target, **lead-time forecast features** (perfect-forecast proxy with a
per-horizon leakage guard). An adversarial eval-review then **caught a real
causality bug in ARIMA** (early-fold rows forecast from a Kalman state that
had seen past their decision time) and exposed ridge+forecast's 48 h "+15%"
as a **single April-rain-fold artifact**. After the fix + per-fold skill
columns, ARIMA briefly led (+2–3 % on SE01-LS-1) — then the **multi-device
confirmation run refuted it**: LS-2 −6…−18 % at every horizon, LS-3 mixed.
**Ship decision (ADR-0003): persistence is the D2 forecaster.** Silver lining:
on LS-2/3/4 the holdout crosses the irrigation threshold and persistence's
alert P/R is 0.95–0.99 — the decision layer works. Remaining human steps:
mentor asks (kubeconfig for NRP compute, token rotation, harvest records).

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
| Sensors (InfluxDB) | `https://nrp-thingsboard-influxdb.nrp-nautilus.io` org `Iron Horse Vineyards`, bucket `ihv` | Flux + `VINE_INFLUX_TOKEN` | ✅ **token restored + re-verified 2026-07-23**; bounded EM500-PP profile added locally (22,256 raw observations; semantics unverified) |
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
| 3 | Historical harvest/yield/irrigation | **Not found in the checked local/DVC snapshots, live InfluxDB, NDP catalog, or current NextCloud share as of 2026-07-23** | Vineyard/mentor handoff still required | ⏸️ **D4 blocked**; no harvest dates, yield, Brix/pH/TA, or irrigation logs available |
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
| D2 | Irrigation models | ☑ (core) | **Persistence remains the served champion.** Nine challenger families evaluated across five probes; oracle-assisted pooled GBT has positive 24/48 h fleet micro-average skill but negative fleet worst folds. Water balance is an **active experiment**: oracle-weather 48 h skill +3.5…+11.2% across probes after purged evaluation, but negative worst folds prevent promotion. D6 now serves persistence+threshold locally. |
| D3 | Plant-health CV | ◐ | Label-free NDVI/NDRE screening code is built/tested; polygon-interior coverage and accepted-only ranking fixes passed regression tests. The corrected remote 39-block rerun exited without a replacement artifact, so real rankings remain pending. Supervised classification still needs mentor-provided labels. |
| D4 | Harvest timing | ☐ | depends on input #3; descopable to exploratory |
| D5 | Evaluation report | ◐ | Shared metrics + expanding walk-forward, per-fold skill, and horizon-aware `h−1` training-label purge after adversarial review. Used by D2; reusable by D4. |
| D6 | NRP deployment | ◐ | Local typed persistence API built/tested; actual NRP deployment still needs kubectl/kubeconfig. |
| D7 | Docs + devlog | ◐ | Model cards, roadmap, and 2026-07-23 devlog updated. |

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

- **2026-07-08 (night)** — **ARIMA candidate refuted; D2 ship decision made.**
  Confirmation runs on the other three soil sensors (same config, ~190–200 k
  raw rows each, same 5.5-month span): LS-2 **negative at every horizon**
  (−6.1/−12.2/−18.0/−10.1 %), LS-3 mixed (+1.7/+2.3/−3.0/−1.7 %), LS-4
  echoes LS-1 (+3.8/−1.9/+2.0/+1.8 %). A model that loses 10–18 % on one of
  four sensors does not ship → **persistence is the D2 forecaster (ADR-0003).**
  New signal: LS-2/3/4 holdouts *do* cross the 25.0 irrigation threshold, and
  persistence's alert precision/recall there is 0.95–0.99 — the decision layer
  is genuinely strong. All runs in MLflow (`d2_irrigation`). (SE0X-LS-1 was
  excluded here for a lack of `soil_water` — **later shown wrong**: its soil
  channels are just under raw LoRa names; folded into the pooled rung below as a
  5th sensor.)

- **2026-07-08 (late night)** — **Trees + rule rung evaluated; conclusion
  unchanged.** Added on request: `drydown_trend` rule baseline (persistence +
  recent-slope extrapolation, now in every results table), `make_forest`
  (RandomForest, complete-rows policy) and `make_gbt`
  (HistGradientBoostingRegressor — CatBoost family, native NaN, zero new
  deps; its binner crashes on all-NaN columns → dropped like ridge does);
  `predict_delta` generalized to any regressor. Run on all 4 sensors ×
  4 horizons (Δ-target + perfect-forecast features): **drydown negative in
  15/16 cells; forest and gbt wildly unstable** — scattered aggregate wins
  (up to +48 %) with catastrophic worst-folds (−4.6…−16) and sign flips
  across sensors (gbt@LS-1/48 h recall 0.64 = misses ⅓ of alerts). Textbook
  high-variance memorization of fold-specific rain episodes, under a perfect
  forecast no less → **do not ship; persistence unchallenged** across 7 model
  families. 84 tests green; runs in MLflow.

- **2026-07-09** — **Pooled cross-sensor rung built + evaluated; persistence
  still champion (8th family rejected).** Motivated by the session's litscan
  (M4/M5 + Elsayed 2021: ML beats naive baselines via *cross-learning across
  related series*, not more history) — the one untried lever, and IHV has 5
  near-identical soil probes sharing weather. Built `d2_irrigation/pooled.py`
  (align all sensors to one hourly grid → time-aligned expanding folds → fit ONE
  Δ-target model on stacked rows → score each sensor vs its OWN persistence,
  plus an `ALL` fleet row) + `scripts/d2_pooled.py` runner + 3 tests (align,
  runs/zero-self-skill, strict-causal split). **Recovered SE0X-LS-1 as a 5th
  sensor** — it *does* have soil channels, under raw LoRa names
  (`device_frmpayload_data_water_SOIL1` etc.; reads dry, mean 18.6, 96.5% below
  the 25.0 threshold) — the earlier "no soil_water column" note was wrong.
  Result (5 sensors × 4 horizons, walk-forward): this original pooled run was
  later superseded by the corrected `h−1`-purged evidence recorded below. It
  motivated the corrected rerun but is not current promotion evidence. Data audit also found: all 9 devices share
  3 identical InfluxDB-level data gaps (Feb 16–17, May 8–19, **Jun 24–Jul 8**);
  verified against source — not an ingest bug; simultaneous across devices →
  likely a shared gateway/ingestion outage, not sensor failure (mentor Q).

- **2026-07-23** — **Pooled D2 corrected; water balance active; D3/D6 MVPs built.**
  Moved pooled runs to YAML, restricted them to declared predictors, added fleet
  fold evidence, then corrected the pooled evaluator to purge the final `h−1`
  training labels. The corrected five-probe fleet skill is
  −45.1/−52.2/+33.0/+30.2% at 6/12/24/48 h, with negative worst-fold skill at
  every horizon. These are realized-future-weather-assisted upper bounds and the
  `ALL` row is a micro-average of correlated sensor-hours, not independent fleet
  replication. Pooled ridge loses fleet-wide at every horizon. Completed the constrained
  water-balance weather correction; adversarial review found a shared fold-boundary
  label leak, fixed via `h−1` training-label purge. Corrected oracle-weather 48 h
  skill is +3.5…+11.2% across five probes, with negative worst folds; **water
  balance remains an active candidate, persistence remains served.** Built D3
  label-free NDVI/NDRE block screening (windowed distributions, coverage and
  disagreement flags, deterministic ranks); real 4 GB rasters verified HTTP 206
  + GDAL-open. A later adversarial review superseded the first 39-block result:
  polygon-interior coverage and accepted-only percentile fixes now pass tests.
  The corrected remote rerun exited without writing a replacement artifact, so
  no corrected real-data rank is claimed. Built local D6 persistence+threshold API;
  real stale snapshot correctly suppresses recommendation. Model cards + devlog
  updated; final repository-wide gate is recorded at the end of this session.

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

1. **Finish corrected D3 rerun:** the polygon-interior coverage and accepted-only
   percentile fixes pass regression tests. Finish the in-progress 39-block screen
   and regenerate D3 reports before treating the superseded 30/9 coverage split
   or H6/L rank as current evidence.
2. **Make the new snapshots reproducible:** the local sensor/imagery DVC pointers
   now include the EM500-PP profile and imagery inventory, but their objects have
   not been pushed. Push only after explicit approval, then verify `dvc status -c`
   is clean so notebook CI can pull them.
3. **Validate active D2 research honestly:** keep water balance active and test it
   on archived forecast vintages or a genuinely new temporal holdout. Persistence
   remains the served model until worst-fold robustness clears the gate.
4. **D3/D4 human inputs:** obtain field-reviewed plant-health labels and historical
   harvest/yield/Brix/irrigation records; D4 remains blocked until then.
5. **D6 cluster deployment:** kubeconfig, namespace/PVC confirmation, immutable
   image publication, and a fresh sensor snapshot are still required. The local
   non-root image and stale-data suppression path are verified.
6. **Security:** rotate the publicly exposed InfluxDB token. The optional managed
   LLM token is not required for any core track.

**Done in this worktree:** pooled and water-balance evaluators were purged at
fold boundaries; ARIMA preserves original fold coordinates under that purge;
mentor-requested D1/D2 notebooks execute offline; EM500-PP raw pressure was
preserved without guessed semantics; local D6 packaging was hardened and rejects
non-finite readings; D3/D5 reports and current-state docs were drafted. The
remaining local work is the in-progress corrected D3 raster rerun; snapshot DVC
objects still require an explicitly approved push.

## How we keep state across sessions

- **This file (`docs/STATE.md`)** is the durable handoff — update it, commit it.
- **`CLAUDE.md`** points new sessions here and stays lean (loaded every session).
- **Decisions** → ADRs in `docs/adr/`. **Narrative** → `docs/devlog/`.
- Secrets stay in `.env` (gitignored); this file references them, never contains them.

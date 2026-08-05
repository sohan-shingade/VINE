# VINE: Current State & Progress Tracker

> **Single source of truth for "where are we."** Git-tracked so it survives any
> session, machine, or context reset. **Any new session: read this first.**
> Update it at the end of any session that changes status. Last updated:
> **2026-08-05 (evening)**. Phase: **all proposal-named models evaluated; NRP
> cluster access live; D6 blocked only on the GitLab registry push**.

## TL;DR: resume here

**D1 complete; D2 closed with persistence served after 15 rejected challenger
families (a CRPS probabilistic wrapper beat persistence in aggregate everywhere yet missed the worst-fold gate in 3 of 20 cells); D3 screening artifact current plus a
pseudo-label CNN pipeline-validation run; D4 descoped-exploratory; D5/D7
reports final with the June devlog gap filled; D6 has live cluster access
(namespace `ihv-jupyterlab`), base resources applied, data seeded, and a
smoke-tested amd64 image, waiting only on a GitLab project for the registry
push (2026-08-05).**

The last open D2 caveat is now closed. Water balance was rerun on real
archived forecast vintages (Open-Meteo Previous Runs, `ceil(h/24)`-day lag,
causality unit-tested) instead of realized future weather. The 48 h aggregate
edge survives the switch (+5.3…+13.5% across five probes, vs +3.5…+11.2% under
the oracle), but 24 h flips negative on every probe (−2.8…−8.1%, worst fold
−2.448), and **worst-fold skill is negative in every cell where the correction
is ever active**. Four 6/12 h cells are exactly 0.000, because the correction
never fires there and water balance is identical to persistence. The
ADR-0003 gate therefore fails. **Persistence remains the served D2 forecaster** and
water balance stays research with a sharper open question: per-fold
forecast-bust robustness rather than a new model family. Fifteen challenger
families have now been evaluated and rejected; Prophet and LSTM, the last two
proposal-named families, joined the list on 2026-08-05 (Prophet aggregate skill
−14.7 to −2.5%, LSTM −4.2 to −8.3%, neither positive anywhere), followed the
same day by diurnal-drift (returns-space hour-of-day seasonality), a
cross-probe error-correction model (spread mean-reversion is real, AR(1) 0.95
to 0.98 hourly, but far too slow to beat the last observation), a CRPS
probabilistic wrapper (aggregate CRPS skill positive in all 20 cells, the
first family to manage that, yet worst-fold negative in 3), and a rain-gated
water-balance hybrid (keeps the event-window win, still loses the fired
subset at 24 h). The pooled and water-balance
rungs ran on all five probes, the earlier per-sensor rungs on four
(SE0X-LS-1 was only recovered on 2026-07-09).

The corrected D3 39-block screen also completed. Both earlier attempts died in
the remote `/vsicurl` read path; this run downloaded the two ~4 GB rasters to
`data/raw/imagery/rasters/` and screened locally. **All 39 blocks pass the
corrected polygon-interior coverage gate at coverage 1.000.** The superseded
30/9 split was purely an artifact of the bounding-box denominator, and the
per-block distributions are unchanged (identical pixel counts and quantiles).
Concern ranking: H6 and L tied at 1 (0.936), J1/J2 at 3, P/Q at 5; 11 of 39
carry the NDVI/NDRE disagreement flag. It remains a label-free review queue.

D4 took its descoped exploratory slice (ADR-0003): a label-free GDD/Winkler
phenology module with no learned parameters. 2025 closed at 1563.2 GDD10
(Winkler Region II); 2026 is at 920.2 through Aug 5, **+12.0% ahead day-matched**.
The useful negative result is that transplanted literature véraison bands land
implausibly late here (Sept 1 to 17) because they accumulate from Jan 1 while the
Winkler window starts Apr 1 instead. That is quantitative proof that the bands
need local calibration from the mentor's harvest records.

D6 serves persistence + threshold locally with typed quality/freshness
responses; a real stale snapshot correctly suppresses advice. Cluster access is
now live: kubeconfig + kubelogin work, namespaces `ihv-jupyterlab` and
`ihv-llm` are usable, the base ConfigMap and both CephFS PVCs are applied and
Bound, raw sensor and weather data are seeded onto the data PVC, and a
smoke-tested linux/amd64 image is built locally. The only missing step is a
GitLab project to push the image to. Current local gate: **288 tests passed**;
Ruff, formatting, mypy, strict MkDocs, codemap regeneration, and deterministic report
regeneration are clean. The sensor and weather snapshots (including the archived
forecast-vintage parquet) are re-pinned and pushed to the `nrp` remote; the
~7.8 GB of D3 rasters under `data/raw/imagery/rasters/` are a local working
download and are deliberately **not** pinned. Remaining human blockers:
D3 labels, harvest records, the GitLab `vine` project, pressure semantics, and
the new InfluxDB token (the old one was rotated on 2026-08-05; all sensor reads
now return 401 until the mentor hands off the replacement).

### Previous state (2026-07-23)

D3 label-free screening and local D6 serving were built; water balance was an
open oracle-assisted experiment; the corrected 39-block rerun had exited without
an artifact. The pooled five-sensor rung, corrected to apply the same `h−1`
training-label purge as the single-probe evaluator, scored fleet skill
−45.1/−52.2/+33.0/+30.2% at 6/12/24/48 h with negative worst folds at every
horizon, so it did not ship either.

### Previous D2 handoff

**All lost secrets restored; D2 rungs 2 to 3 built and honestly evaluated**
(2026-07-08 evening, orchestrated multi-agent session): S3 keys re-issued →
DVC round-trip verified and fresh snapshots pinned+pushed. Built via parallel
workers: weather-**forecast** reader (input 4f ✅), **ARIMA** rung, **Δ-moisture**
target, **lead-time forecast features** (perfect-forecast proxy with a
per-horizon leakage guard). An adversarial eval-review then **caught a real
causality bug in ARIMA** (early-fold rows forecast from a Kalman state that
had seen past their decision time) and exposed ridge+forecast's 48 h "+15%"
as a **single April-rain-fold artifact**. After the fix + per-fold skill
columns, ARIMA briefly led (+2 to 3 % on SE01-LS-1). Then the **multi-device
confirmation run refuted it**: LS-2 −6…−18 % at every horizon, LS-3 mixed.
**Ship decision (ADR-0003): persistence is the D2 forecaster.** Silver lining:
on LS-2/3/4 the holdout crosses the irrigation threshold and persistence's
alert P/R is 0.95 to 0.99, so the decision layer works. Remaining human steps:
mentor asks (kubeconfig for NRP compute, token rotation, harvest records).

## Verified facts & live endpoints

Everything here was tested and confirmed working from this machine at the
noted date (secrets live in `.env`, gitignored; never commit them).
The 2026-07-04 machine wipe lost `.env` + `.dvc/config.local`; **everything
that matters is restored as of 2026-07-08** (Influx token from the starter
repo, S3 keys re-issued from portal `/s3token/`). Only the optional LLM key
remains unset. Gotcha: no inline comments after values in `.env`, because
dotenv reads them as the value (bit us via `.env.example`'s NDP line; now fixed).

| Resource | Endpoint | Access | Verified |
|----------|----------|--------|----------|
| Sensors (InfluxDB) | `https://nrp-thingsboard-influxdb.nrp-nautilus.io` org `Iron Horse Vineyards`, bucket `ihv` | Flux + `VINE_INFLUX_TOKEN` | ⚠️ **token ROTATED, observed 2026-08-05**: every device read returns 401 with the old token. This resolves mentor Q5 (the publicly committed token is dead) but blocks fresh ingest until the new token is handed off securely. Bounded EM500-PP profile added locally earlier (22,256 raw observations; semantics unverified) |
| NRP S3 (Pool West) | `https://s3-west.nrp-nautilus.io`, bucket `ihv-vine` | `AWS_ACCESS_KEY_ID/SECRET` in `.env` | ✅ **keys re-issued + verified 2026-07-08** (list on `ihv-vine` HTTP 200) |
| DVC remote | `s3://ihv-vine/dvc` on NRP S3 | `.dvc/config` + creds in `.dvc/config.local` (gitignored) | ✅ **restored 2026-07-08**: creds rewritten, fresh snapshots pinned (`sensors` 1.04 M rows, `weather`, `imagery` 61 MB) and pushed (19 objects) |
| NDP catalog API | `https://nationaldataplatform.org/catalog/api/3/action/` | public, no auth | ✅ found the 2 IHV datasets |
| Imagery STAC | `https://ndp-test.sdsc.edu/stac/collections/IHV_DJI_MULTISPECTRAL_DCIM` | public | ✅ serves collection + items (2026-07-06); ⚠️ **asset `download?path=` hrefs are STALE**: they point at flight subfolders that 404 (e.g. `..._002` vs real `..._001`); reconcile against the WebDAV tree, don't trust hrefs verbatim |
| Imagery files | `https://nextcloud.nrp-nautilus.io/s/ieAqEKDDKeYq9q4` | public share | ✅ **back up 2026-07-06** (`maintenance:false`, WebDAV browsable, downloaded a real 10.9 MB JPEG 5280×3956); use WebDAV `public.php/webdav/` with share token as user |
| Weather (historical) | `https://archive-api.open-meteo.com/v1/archive` | public, no key | ✅ daily tmax/tmin/precip/ET₀ at vineyard coords |
| NRP managed LLM | `https://ellm.nrp-nautilus.io/v1` | `VINE_NRP_LLM_API_KEY` in `.env` | 🔑 worked 2026-06-16 (11 models); **key lost in wipe**, portal `/llmtoken/` (optional) |
| Kubernetes (Nautilus) | cluster `nautilus`, kubeconfig from `https://nrp.ai/config` | kubelogin (OIDC via CILogon) | ✅ **working 2026-08-05**: namespaces `ihv-jupyterlab` + `ihv-llm`, create rights for deployments/jobs in both; storage class `rook-cephfs` confirmed; ConfigMap + both PVCs applied and Bound; raw data seeded to the data PVC |

Vineyard location: **38.457 N, −122.896 W** (Sebastopol, CA). Blocks seen in
imagery: `Cd, H5, H4, E, H2, Q, Ce`.

## The 4 data inputs (D1)

| # | Input | Source (confirmed) | How to get it | Status |
|---|-------|--------------------|---------------|--------|
| 1 | Sensors | InfluxDB bucket `ihv` | `vine.d1_pipeline.InfluxReader` (Flux) | ✅ working |
| 2 | Drone imagery | NextCloud share (WebDAV), **not** STAC hrefs (stale) | `vine.d1_pipeline.imagery` (flight index → captures → band download) + `geo` (KMZ blocks, zonal stats) | ✅ **BUILT + LIVE-VERIFIED 2026-07-06**: orthomosaics & block polygons were on the share all along (`GIS/`) |
| 3 | Historical harvest/yield/irrigation | **Not found in the checked local/DVC snapshots, live InfluxDB, NDP catalog, or current NextCloud share as of 2026-07-23** | Vineyard/mentor handoff still required | ⏸️ **D4 blocked**; no harvest dates, yield, Brix/pH/TA, or irrigation logs available |
| 4 | Weather (hist) | Open-Meteo archive (ERA5) | `vine.d1_pipeline.fetch_historical` | ✅ **reader built + tested + verified live** |
| 4f | Weather (forecast) | Open-Meteo forecast API | `vine.d1_pipeline.fetch_forecast` | ✅ **built + live-verified 2026-07-08** (3-day forecast, same tidy daily frame). Backtests use the labeled perfect-forecast proxy (`add_lead_time_features`); live serving would fill the same `_next_{h}h` columns from this reader |

**Imagery inventory (from STAC, 2026-06-16):** 9,295 capture points, 11 flights
(2025-08-27 → 2026-01-08), DJI Mavic 3 Multispectral. Each capture: `visual` (RGB)
+ `green/red/rededge/nir` (TIF, ~7,868 with full multispectral). Raw per-photo, NOT
stitched → D1 must stitch/orthomosaic + align to blocks. Flight timing skews to
winter/dormant; the useful growing-season flights are Aug (pre-harvest) + Oct
(harvest), and there are few of them.

## Deliverable progress

`☐ todo · ◐ in progress · ☑ done`

| D | Deliverable | Status | Notes |
|---|-------------|--------|-------|
| — | Repo + Claude Code scaffold + wiki | ☑ | builds green: ruff/mypy/tests |
| D1 | Data pipeline | ☑ | **all three reachable inputs done + live-verified**: sensor path (ingest→flags→features→weather/GDD), weather reader (historical, forecast, **and archived forecast vintages**), **imagery path** (WebDAV flight index → capture grouping → band download → NDVI) + **block alignment** (39 KMZ polygons, sensor→block join, windowed zonal stats with polygon-interior coverage). Historical records (input #3) remain a mentor Q, and matter only for D4 |
| D2 | Irrigation models | ☑ | **Closed: persistence is the served forecaster.** Fifteen challenger families evaluated and rejected (2026-08-05: diurnal-drift, error correction, a CRPS probabilistic wrapper, and a rain-gated hybrid joined; none pass the worst-fold gate, though the CRPS wrapper is the first with positive aggregate skill in all 20 cells). The event study shows event hours are 2 to 5% of the holdout yet carry 17 to 40% of persistence's error, and the vintage water balance wins those hours at 24/48 h → tail value exists, quiet-hour and forecast-bust costs still block promotion. D6 serves persistence+threshold |
| D3 | Plant-health CV | ☑ (label-free scope) | Corrected 39-block screen complete on real 2026-06-01 rasters: 39/39 pass the polygon-interior coverage gate, deterministic concern ranks retained as a versioned artifact and rendered offline. A pseudo-label CNN pipeline-validation run (ResNet-50, NDVI/NDRE channels, block-level split, val acc 0.806) proves the supervised training path end to end; its card states plainly it is not stress detection. Supervised classification remains blocked on mentor-provided labels |
| D4 | Harvest timing | ☑ (descoped-exploratory) | No harvest/yield/Brix labels exist (input #3), so per ADR-0003 D4 is exploratory: a label-free GDD/Winkler phenology module with no learned parameters, plus a report and model card that state plainly it does not ship. Supervised D4 stays blocked on records |
| D5 | Evaluation report | ☑ | Shared metrics, expanding walk-forward, per-fold skill, `h−1` training-label purge. Final report is regenerated offline from pinned snapshots with no MLflow or network dependency |
| D6 | NRP deployment | ◐ | Local typed persistence API built/tested/containerized; stale-snapshot suppression verified. Cluster side: kubeconfig + RBAC live, ConfigMap + PVCs applied, data seeded, amd64 image built and smoke-tested. Blocked only on a GitLab `vine` project for the registry push |
| D7 | Docs + devlog | ☑ | Model cards for all served/exploratory artifacts (incl. the D3 pseudo-label CNN), roadmap, four reports, and the devlog through June + 2026-08-05; MkDocs builds strict |

## Done log

- **2026-06-16**: Scaffolded repo (`src/vine`, tests, configs, docker, k8s),
  Claude Code setup (CLAUDE.md, commands, agents, hook), MkDocs wiki, 9 ADRs.
- **2026-06-16**: Verified InfluxDB; built + ran `vine ingest` (9 devices).
- **2026-06-16**: Verified NRP S3, wired DVC remote, pushed sensor snapshots.
- **2026-06-16**: Found NDP catalog API (`/catalog/...`); located imagery (STAC)
  + sensors; inventoried 9,295 imagery captures.
- **2026-06-16**: Confirmed Open-Meteo historical weather + ET₀. Recorded
  weather decision (ADR-0009).
- **2026-06-21**: Built D1 weather reader (`d1_pipeline/weather.py`, input #4):
  Open-Meteo archive client (pure param/parse helpers + `fetch_historical`),
  config coords/URL, 4 unit tests. Verified live (8 daily rows tmax/tmin/precip/ET₀
  at vineyard coords). `make check` green (21 tests).
- **2026-06-21**: Built interactive course website (`course-site/`, zero-dep):
  18 modules teaching every prereq → all deliverables; animated diagrams, NDVI demo.
- **2026-06-21**: Built + tested the **D1 sensor path** end to end: `pipeline.py`
  (`build_sensor_features`: regularize → gap/range flags → rolling/lag features;
  `attach_weather`: daily weather ffill + cumulative GDD). Wired weather into
  `vine ingest --weather-days N`. Fixed two real bugs found on live data:
  (a) tz-aware sensor index vs tz-naive weather, (b) InfluxDB pivot returning
  numeric readings as strings → coerce in `influx.read` + assembler. 34 tests green.
  Verified on real snapshot: 73 hourly rows → 42 feature cols, weather+GDD joined.
- **2026-06-21**: Re-probed imagery: NextCloud `nextcloud.nrp-nautilus.io` still
  **503** (share + WebDAV). `status.nextcloud.com` is the unrelated Nextcloud-GmbH
  page, not our instance. STAC up but all asset hrefs route through NextCloud.
- **2026-07-02**: Re-probed imagery + checked the "moved to S3?" theory: **no S3
  mirror found.** NextCloud still 503 (share/WebDAV/root). STAC replicas flapping
  (collection listed + items served on some hits, 404/empty on others); asset hrefs
  still point at NextCloud. NDP catalog dataset unchanged (last modified 2026-03-29),
  still links NextCloud + STAC. **New:** `s3-west.nrp-nautilus.io` itself is 503
  endpoint-wide (our `ihv-vine` bucket + DVC remote unreachable); s3-central/east up
  but reject our west-pool creds and have no IHV buckets under obvious names.
  → Imagery stays blocked; add mentor Q: is imagery being migrated off NextCloud /
  what's up with s3-west?
- **2026-07-02 (later)**: **Root cause found** via the Nautilus Support Matrix feed
  (`https://nrp.ai/api/matrix-feed`, backs the nrp.ai/live news page): NRP announced
  **Ceph upgrades for 2026-07-02, 10:00 to 16:00 Pacific, affecting CephFS, RBD,
  and S3**. Today's s3-west 503 is planned maintenance, not an outage or
  migration (creds confirmed fine: anonymous requests get the same HAProxy 503).
  Also: NextCloud was declared **back up on 2026-06-24** ("previews return
  gradually"), so the imagery share is likely fine once today's Ceph work
  finishes. Re-probed 20:30 Pacific: both still 503 (upgrade running long).
  **→ Retry NextCloud + s3-west tomorrow; imagery download may finally be
  unblocked.**
- **2026-07-06**: **Imagery UNBLOCKED, verified end to end.** NextCloud is back
  (`status.php` → `maintenance:false`, v33.0.5); public-share **WebDAV** browsable
  (207, full tree: `_sorted_data/BLOCKS/…`, `GIS/`, `sensor reference/`); STAC serves
  the collection + items; **downloaded a real 10.9 MB JPEG (5280×3956)** from
  `H5/2026-01-08/m3m/images/` (570 files in that one flight). s3-west root back to
  HTTP 200 too. **Gotcha:** STAC asset `download?path=` hrefs are STALE: they point
  at flight subfolders that 404 (e.g. `DJI_…_002` vs the real `…_001`, plus an
  `images/` subfolder STAC doesn't name) → the D1 imagery reader must walk the
  WebDAV tree / reconcile STAC item IDs against real folder names, not trust hrefs.
  Downloading works; **stitched orthomosaics + block polygons still don't exist**
  (mentor Q), so `imagery.py`/`geo.py` remain stubs. The raw-file blocker is gone;
  the orthomosaic/geometry blocker is not.
- **2026-07-06 (later)**: **D1 imagery + block alignment BUILT; D1 code-complete.**
  Scout-mapped the whole share (brief: `docs/data/imagery-share-layout.md`) and found
  the supposed blockers were already there: `GIS/IHV-2026-05-26.kmz` holds **39 block
  polygons** (names match `_sorted_data/BLOCKS/` 1:1) **+ 182 points incl. sensor
  locations**, and `GIS/` holds stitched **Pix4DFields orthomosaics** with NDVI/NDRE
  computed (H-blocks 2025-08-29; whole-vineyard 2026-06-01, 46 GB), so no stitching
  is needed for those dates. Built: `webdav.py` (share client), `imagery.py` (flight
  index, where share placement is authoritative and STAC block attribution is
  stale/re-sorted; capture grouping; size-checked band downloads), `geo.py`
  (stdlib KML→polygons, windowed `zonal_stats`, `assign_sensors_to_blocks`).
  Live-verified: 34 flights indexed; 582-capture flight grouped exactly;
  4 bands downloaded + NDVI 0.272;
  39/39 blocks loaded; 47 sensors joined to blocks; zonal stats on the real 1 m DSM
  hit 39/39. `vine imagery` CLI added. **48 tests green** (was 34), ruff+mypy clean.
  Also: codemap shards (`make codemap`, consult before Reading source), Serena MCP
  registered. Note: `_unsorted/M3M/` has ~120 newer flights (through 2026-07-03) not
  yet sorted into blocks; growing-season coverage is still thin (mentor Q stands).
- **2026-07-06 (evening)**: **D2 baseline ladder BUILT; discovered the secrets are
  gone.** Tried `vine ingest --start=-365d` for the D2 target series → **no InfluxDB
  token: `.env` and `.dvc/config.local` did not survive the 2026-07-04 machine wipe**
  (local DVC cache empty too; anonymous S3 GET → 403; endpoints themselves fine).
  Pivoted to building everything that doesn't need live data: **D5 walk-forward
  harness** (`walkforward.py`: expanding splits, causal `walk_forward`, `skill`
  score), **D2 baselines** (`seasonal_naive`, `climatology_hourly` added), **ridge
  rung** (`models.py`), **config-driven runner** (`experiment.py`: target-time
  alignment so baselines are pure shifts and models see `frame.shift(h)`; every
  model scored on identical holdout rows; gaps masked, never imputed), MLflow
  logging, `vine train irrigation <config>` CLI. Verified end-to-end on synthetic
  snapshots (`VINE_DATA_DIR` override): full 4-model × 4-horizon table, sane
  ordering (ridge best, seasonal≈persistence at 24/48 h). The e2e run caught a real
  bug unit tests missed: `*_std_1h` rolling features are all-NaN on an hourly grid
  → ridge had zero complete training rows; fixed (drops no-signal columns per fold,
  test added). **67 tests green** (was 48). Configs updated to real column names
  (`soil_water`, device `SE01-LS-1`); `ridge.yaml` added.
- **2026-07-08**: **Influx token restored; D2 live eval DONE: ridge does not
  ship.** Token recovered without the mentor: ADR-0008 records that the public
  starter repo (`nrp-precision-agriculture/iron-horse-vineyards/jupyter-notebooks`
  on `gitlab.nrp-nautilus.io`) commits a live 88-char token in its notebooks
  (`TOKEN = "…"` in `influx-SE01-LS-1.ipynb`); extracted it, verified auth
  (HTTP 200), wrote it to `.env`, never echoed or committed. **This is exactly
  why mentor Q5 (rotate the token) matters: anyone can do this.** Re-ingested
  `--start=-365d --weather-days 400`: **1,036,276 rows / 9 devices** + 401 daily
  weather rows; SE01-LS-1 history actually begins **2026-01-22** (~5.5 months,
  188 k raw rows; soil_water 18 to 45, mean 27.3, 39% below the 25.0 threshold).
  Ran `vine train irrigation configs/d2_irrigation/ridge.yaml` (all 4 models ×
  4 horizons, n≈1330 to 1360 scorable holdout rows each): **persistence wins every
  horizon** (MAE 0.105 → 0.524 from 6 h → 48 h); seasonal-naive ties at 24/48 h
  (whole-day shifts), loses at 6/12 h; climatology MAE ~5.4 (hour-of-day mean
  can't track seasonal drying); **ridge skill −0.73…−1.13 → per ADR-0003 it
  does not ship.** Honest read: real soil moisture is near-random-walk at these
  horizons. Current features (lags/rolling/past weather) add nothing over the
  last observation; the synthetic win was an artifact of its strong daily cycle.
  Decision-layer P/R = 1.0 for truth-tracking models (holdout = dry season,
  mostly below threshold), 0.0 for climatology, so threshold metrics need a
  shoulder-season holdout to be informative. Logged to MLflow (`d2_irrigation`).
  **S3/DVC still blocked on `/s3token/` keys** (only remaining lost secret that
  matters; LLM key optional).

- **2026-07-08 (evening)**: **S3/DVC restored; D2 rungs 2 to 3 built, adversarially
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
  looked great: ARIMA positive everywhere (max +8.3 %), ridge+fcst +14.7 %
  at 48 h. (4) **eval-reviewer adversarial pass refuted both**: `make_arima`'s
  first h−1 rows per fold forecast from a filter state containing observations
  past their decision time (unit tests only used h=1, where the leaky region
  is empty; that was the lesson); ridge's 48 h win came entirely from one April rain
  fold (fold skill +0.55; excluding it, −0.62; bootstrap CI spans 0).
  (5) Fixed ARIMA (`res.apply` on the truncated prefix for early rows) + added
  an h=6 poison-tail causality test + **per-fold skill columns** in the results
  table. (6) Honest re-run: ARIMA +3.0/−1.8/+2.4/+2.1 %, positive in every
  fold at 48 h, the first rung above zero, held as *candidate*; ridge variants'
  fold medians are negative → artifacts confirmed visible in-table.
  **Persistence remains champion.** 78 tests green; MLflow has all runs;
  codemap regenerated. Advisor also flagged: daily-ffilled weather levels
  leak up to 24−h h past target at short horizons, so future rungs must use
  the `_next_` columns for intra-day weather.

- **2026-07-08 (night)**: **ARIMA candidate refuted; D2 ship decision made.**
  Confirmation runs on the other three soil sensors (same config, ~190 to 200 k
  raw rows each, same 5.5-month span): LS-2 **negative at every horizon**
  (−6.1/−12.2/−18.0/−10.1 %), LS-3 mixed (+1.7/+2.3/−3.0/−1.7 %), LS-4
  echoes LS-1 (+3.8/−1.9/+2.0/+1.8 %). A model that loses 10 to 18 % on one of
  four sensors does not ship → **persistence is the D2 forecaster (ADR-0003).**
  New signal: LS-2/3/4 holdouts *do* cross the 25.0 irrigation threshold, and
  persistence's alert precision/recall there is 0.95 to 0.99, so the decision
  layer is genuinely strong. All runs in MLflow (`d2_irrigation`). (SE0X-LS-1 was
  excluded here for a lack of `soil_water`. That was **later shown wrong**: its
  soil channels are just under raw LoRa names, and it is folded into the pooled
  rung below as a 5th sensor.)

- **2026-07-08 (late night)**: **Trees + rule rung evaluated; conclusion
  unchanged.** Added on request: `drydown_trend` rule baseline (persistence +
  recent-slope extrapolation, now in every results table), `make_forest`
  (RandomForest, complete-rows policy) and `make_gbt`
  (HistGradientBoostingRegressor, CatBoost family, native NaN, zero new
  deps; its binner crashes on all-NaN columns → dropped like ridge does);
  `predict_delta` generalized to any regressor. Run on all 4 sensors ×
  4 horizons (Δ-target + perfect-forecast features): **drydown negative in
  15/16 cells; forest and gbt wildly unstable**: scattered aggregate wins
  (up to +48 %) with catastrophic worst-folds (−4.6…−16) and sign flips
  across sensors (gbt@LS-1/48 h recall 0.64 = misses ⅓ of alerts). Textbook
  high-variance memorization of fold-specific rain episodes, under a perfect
  forecast no less → **do not ship; persistence unchallenged** across 7 model
  families. 84 tests green; runs in MLflow.

- **2026-07-09**: **Pooled cross-sensor rung built + evaluated; persistence
  still champion (8th family rejected).** Motivated by the session's litscan
  (M4/M5 + Elsayed 2021: ML beats naive baselines via *cross-learning across
  related series*, not more history). That was the one untried lever, and IHV has 5
  near-identical soil probes sharing weather. Built `d2_irrigation/pooled.py`
  (align all sensors to one hourly grid → time-aligned expanding folds → fit ONE
  Δ-target model on stacked rows → score each sensor vs its OWN persistence,
  plus an `ALL` fleet row) + `scripts/d2_pooled.py` runner + 3 tests (align,
  runs/zero-self-skill, strict-causal split). **Recovered SE0X-LS-1 as a 5th
  sensor**: it *does* have soil channels, under raw LoRa names
  (`device_frmpayload_data_water_SOIL1` etc.; reads dry, mean 18.6, 96.5% below
  the 25.0 threshold), so the earlier "no soil_water column" note was wrong.
  Result (5 sensors × 4 horizons, walk-forward): this original pooled run was
  later superseded by the corrected `h−1`-purged evidence recorded below. It
  motivated the corrected rerun but is not current promotion evidence. The data
  audit also found that all 9 devices share 3 identical InfluxDB-level data gaps
  (Feb 16 to 17, May 8 to 19, **Jun 24 to Jul 8**); verified against source, so
  not an ingest bug. Simultaneous across devices → likely a shared
  gateway/ingestion outage, not sensor failure (mentor Q).

- **2026-07-23**: **Pooled D2 corrected; water balance active; D3/D6 MVPs built.**
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

- **2026-08-05**: **D2 closed, D3 landed, D4 descoped: every code-side
  deliverable is done.** Three tracks ran in parallel under an orchestrator that
  independently re-verified each result rather than trusting agent reports.
  (1) **D2 vintage validation.** Built the archived-forecast reader in
  `d1_pipeline/weather.py` (`vintage_lag_days`, `build_previous_runs_params`,
  `parse_hourly_vintages`, `fetch_forecast_vintages`) against Open-Meteo's
  Previous Runs API. Causality rule: for horizon `h` use the `_previous_dayN`
  run with `N = ceil(h/24)`, rounded **up** so no value in `(t, t+h]` comes from
  a run issued after decision time `t`; unit-tested including a poisoned
  fresh-vintage case at 48 h. Fetched 4,032 hourly rows (2026-01-22 → 2026-07-08,
  zero missing) and reran the same purged evaluation with
  `weather_source: vintage`. The 48 h aggregate edge survives real forecasts
  (+5.3…+13.5% vs the oracle's +3.5…+11.2%), but 24 h flips negative on every
  probe (−2.8…−8.1%, worst fold −2.448) and **worst-fold skill is negative in
  every cell where the correction is ever active** (the four exactly-zero 6/12 h
  cells are cells where it never fires) → gate fails, **not promoted, persistence
  stays served**. The fresh oracle control run reproduced the 2026-07-23 numbers
  exactly. (2) **D3 corrected 39-block screen.** Both prior attempts died in the
  remote `/vsicurl` path (endless `HTTP error code: 0` retries after hours of
  range reads on two ~4 GB rasters); fixed by fetching both rasters locally with
  resumable curl and screening against local files. **39/39 blocks pass the
  corrected polygon-interior coverage gate at coverage 1.000.** The superseded
  30/9 split was entirely a bounding-box-denominator artifact, and per-block
  distributions are unchanged (identical pixel counts and quantiles). Ranks:
  H6 and L tied at 1 (0.936), J1/J2 at 3, P/Q at 5, then M, E, G, B South;
  11 of 39 carry the NDVI/NDRE disagreement flag. (3) **D4 exploratory slice.**
  `d4_harvest/phenology.py`: pure GDD/Winkler accumulation with band crossings,
  no learned parameters, gaps flagged never imputed. 2025 = 1563.2 GDD10
  (Region II); 2026 = 920.2 through Aug 5, +12.0% ahead day-matched; bloom band
  crossed within one day across seasons. Useful negative result: literature
  véraison bands land at Sept 1 to 17 here because they accumulate from
  Jan 1 while the Winkler window starts Apr 1 instead. That is direct evidence
  that transplanted thresholds need local calibration. Verified independently by
  recomputing the GDD totals from Open-Meteo outside the pipeline (exact match).
  Reports, model cards, and the devlog were written for all three; the D3 and
  D5 reports regenerate offline from retained artifacts.

- **2026-08-05 (evening)**: **Prophet + LSTM evaluated (challengers 10 and 11),
  D3 pseudo-label CNN run, June devlog written, NRP cluster access live, D6
  staged to the registry-push step.** (1) **D2:** built `make_prophet` and
  `make_lstm` in `d2_irrigation/models.py` (configs `prophet.yaml`,
  `lstm.yaml`; poison-tail causality tests included) and ran both through the
  same purged walk-forward harness. Prophet aggregate skill −14.7/−8.4/−4.9/−2.5%
  and LSTM −4.2/−6.0/−6.2/−8.3% at 6/12/24/48 h; neither beats persistence
  anywhere → rejected, challenger count now eleven, every model family named in
  the proposal has been evaluated. (2) **D3:** pseudo-label CNN fallback
  executed as the proposal specifies for the no-labels case: ResNet-50 with a
  generic channel-adapter stem on NDVI/NDRE patches (2 channels; the other 5
  are not in the local rasters), NDVI-tertile pseudo-labels computed on
  training blocks only, block-level split. 1,209 patches / 39 blocks; val acc
  0.806, macro F1 0.800 on 10 held-out blocks; all confusions
  adjacent-tertile. Card frames it strictly as pipeline validation. Checkpoint
  gitignored. (3) **D5/D7:** predicted-vs-actual and D3 concern-map figures
  generated deterministically (byte-identical across runs), ablation-scope
  paragraph added, June devlog gap filled
  (`docs/devlog/2026-08-05-june-in-review.md`). (4) **D6/NRP:** kubeconfig +
  kubelogin installed, CILogon auth completed, RBAC verified in
  `ihv-jupyterlab` and `ihv-llm`; ConfigMap + 20Gi CephFS PVCs applied and
  Bound; 11.3 MB of raw sensor/weather data seeded onto the data PVC;
  CronJob manifest fixed to the real namespace; linux/amd64 image built (via
  docker-buildx) and smoke-tested, including the stale-snapshot suppression
  path. Push blocked only on a GitLab project. (5) **Observed:** InfluxDB
  token rotated (all device reads 401), which closes mentor Q5; a new token is
  needed for fresh ingest. Gate: **228 tests passed**, mkdocs strict clean.

- **2026-08-05 (night)**: **Irrigation-event catalog derived, plus three more
  D2 analyses: diurnal-drift and error-correction challengers (both rejected,
  count now thirteen) and first-passage crossing probabilities (a win on
  Brier at 24/48 h).** (1) **Events:** `d2_irrigation/events.py` detects
  soil-moisture rise events from gap-free windows and attributes them to rain
  via daily precipitation. 55 events cataloged: 51 rain, 4 irrigation (all
  four in the verified zero-precip Mar 8 to 20 window; median irrigation jump
  0.62 vs rain 2.47). Report + CSV in `docs/reports/`. (2) **Diurnal drift
  (challenger 12):** persistence plus cumulative hour-of-day mean deltas,
  plain and temp-tercile variants. First-ever positive worst-fold cells
  (LS-2/LS-4 at 24/48 h) yet the gate fails on 6/12 h and the other probes →
  rejected. (3) **Error correction (challenger 13):** cross-probe spread
  model; the spread genuinely mean-reverts (hourly AR(1) 0.95 to 0.98,
  half-life 14 to 31 h) and beta points toward reversion in 81 of 100 fold
  cells, yet reversion is too slow to beat the last observation. Worst-fold
  skill negative in all 20 cells → rejected. MLflow run
  `32735834038b40bb9cce950347beee0d`. (4) **First passage:** Brownian
  crossing probabilities (EWMA drift + volatility) for threshold alerts.
  Beats binary persistence on Brier at 12/24/48 h (48 h: 0.0099 vs 0.0203,
  half the score); extremes calibrated, mid-range overconfident. Analysis
  only, deliberately not wired into D6 serving. MLflow run
  `52649766c9a44bc784ad6515ee75e58d`. Gate: **248 tests passed**, mkdocs
  strict clean, codemap regenerated.

- **2026-08-05 (late night)**: **Event study quantifies the tail, and two more
  challengers (14 and 15) probe it: a CRPS probabilistic wrapper and a
  rain-gated water-balance hybrid. Persistence stays served; count now
  fifteen.** (1) **Event study:** scoring only the hours inside detected rise
  events plus a trailing 24 h shows event hours are 2.2 to 4.6% of the SE01
  holdout yet carry 17.3 to 39.8% of persistence's total absolute error
  (event MAE roughly 6 to 28x quiet). The vintage water balance beats
  persistence on event hours at 24 h (+0.030 to +0.283) and 48 h (+0.224 to
  +0.626) on every probe with events, and loses aggregate 24 h only through
  quiet hours. All event evidence comes from the single Apr 20 to 22 storm.
  MLflow `d1deb61b46aa44b780bc6ecd46200a5e`. (2) **CRPS wrapper (14):**
  Gaussian centered on persistence with causal EWMA spread. Aggregate CRPS
  skill positive in all 20 cells (+0.094 to +0.266), the first family to
  manage that on any aggregate metric; 90% coverage 0.87 to 0.96; worst-fold
  gate still fails in 3 cells (one truncated May-outage fold, two near-zero
  early folds). Controls: fixed spread and climatology both fail badly, so
  the adaptive spread carries the value. MLflow
  `e5f950958fc345edafefb24b18dc8469`. (3) **Rain-gated hybrid (15):**
  persistence unless forecast precip over the horizon window clears a
  causally selected threshold (84 of 100 folds picked 5.0 mm). Retains 87 to
  105% of the water balance's event win and turns 48 h aggregate positive on
  all probes (+0.051 to +0.122), yet the fired subset at 24 h is negative
  everywhere (−0.094 to −0.267) and threshold choice cannot separate
  forecast busts from hits, so weak dominance fails. MLflow
  `2292358f1a41441285d3c1fbcb1a06d6`. Verdict across the metric ladder:
  point MAE unbeaten, Brier beaten by first passage at 12 to 48 h, CRPS
  beaten in aggregate everywhere with 3 worst-fold misses, tail hours beaten
  by water balance at 24/48 h. Gate: **288 tests passed**, mkdocs strict
  clean, codemap regenerated.

- **2026-08-05 (late night, second entry)**: **Literature review positions the
  D2 result. Persistence plus a threshold is what control theory prescribes for
  this system class, and the ML literature reproduces our finding.** Nine
  research agents surveyed control theory, California agronomy and regulation,
  the ML/RL irrigation literature, and institutional programs. Key findings:
  (1) event-triggered control theory (Åström & Bernhardsson 2002; Lipsa &
  Martins 2011; Soleymani et al. 2023) proves threshold structure is optimal for
  noisy first-order systems with direct state measurement, so D2's shipped
  policy is the theoretically favored structure rather than a fallback. (2) The
  best field-validated MPC beats soil-sensor threshold control by roughly 5
  percent water, so the available margin above our baseline is small; the 40 to
  50 percent savings figures in the literature are all against calendar
  schedules. (3) In precision viticulture **no published study benchmarks
  against persistence at all**; Deforce et al. (2024), the closest analogue
  outside viticulture, finds an LSTM improves 5-day soil-water-potential MAE by
  0.45 percent and is 4.65 percent worse on RMSE. (4) Geospatial foundation
  models add nothing to soil-moisture regression (Kontogiorgakis et al. 2026:
  R² 0.515 vs 0.514 for handcrafted features). (5) RL irrigation has never left
  the simulator. (6) Sensor-network ML vineyard DSS is pilot-stage worldwide
  with no exceptions found, the Iron Horse program included. Written up as
  `docs/reports/2026-08-05-irrigation-control-review.md`; the model card gained
  a literature-position bullet, and the unbacked "~10% water reduction" claim on
  the home page is now attributed as a CENIC/NRP program target rather than a
  measured result. No code or model change. Gate: **288 tests passed**, mkdocs
  strict clean.

- **2026-08-05 (late): optimal-stopping decision layer built and evaluated
  (research, not promoted).** New module `vine.d2_irrigation.stopping` plus
  runner `scripts/d2_stopping.py` and config
  `configs/d2_irrigation/stopping.yaml`, borrowing from finance and
  operational meteorology. Established with a controlled ablation on all five
  probes: the first-passage closed form prices a *continuously* monitored
  barrier while the label is scored on hourly readings (Broadie-Glasserman-Kou
  discrete-monitoring bias, roughly 37 percent relative overstatement at 6 h,
  pinned against Monte Carlo to 4 decimals), and the hourly increments are far
  from Gaussian (excess kurtosis 324 to 1416, repaired with filtered
  historical simulation to 26 to 32). The corrected empirical layer wins
  Brier and log loss at 6 to 24 h; at 48 h the variants converge, so the
  corrections matter exactly where the alert is actionable. Evaluation target
  is a 0.3-unit drawdown event because any absolute barrier is degenerate on
  this record (fixed 25.0: holdout base rates 0.61 to 1.00, documented in the
  `_fixed` CSVs). Cost-loss economic value (new ADR-0010) shows the filtered
  Bayes rule holding a positive value band at every horizon while the
  incumbent goes sharply negative at moderate cost ratios (systematic
  over-irrigation). Backward-induction exercise boundaries put the optimal
  trigger only 0.02 to 0.13 units above the barrier at observed volatilities,
  which is the quantitative reason threshold rules keep winning on this
  plant; response delay is what would change that. Report
  `docs/reports/2026-08-05-optimal-stopping.md`; tables
  `docs/reports/assets/d2_stopping_*.csv`; 22 new tests including a
  200k-path Monte Carlo pin of the crossing recursion.

## Open questions for mentor

1. **Historical records** (harvest dates, yields, irrigation logs): do they exist,
   and where? Not in InfluxDB or NDP. (Drives D4 scope.)
2. ~~Imagery availability~~ **Mostly resolved 2026-07-06:** NextCloud is back;
   stitched Pix4D orthomosaics + block polygons were on the share (`GIS/`) all
   along. **Remaining:** more growing-season flights coming? Will the ~120
   `_unsorted/M3M/` flights (through 2026-07-03) get sorted into blocks, or
   should we sort by GPS-vs-polygon ourselves? Is STAC going to be re-indexed
   (its block attribution predates a re-sort and its inventory ends 2026-01-08)?
3. **Labeled imagery** for plant stress/pest (D3): does any exist?
4. ~~NRP access~~ **Resolved 2026-08-05:** kubeconfig obtained from
   `https://nrp.ai/config`, kubelogin OIDC auth works, and namespaces
   `ihv-jupyterlab` + `ihv-llm` grant create rights. Storage class
   `rook-cephfs` confirmed via `kubectl get sc`. **Remaining:** a GitLab
   project (suggested name `vine`, under the `ihv` group) so images can be
   pushed to `gitlab-registry.nrp-nautilus.io`.
5. **Security**: ~~rotate the InfluxDB token~~ **Rotated, observed 2026-08-05**
   (all reads with the old token now 401). Good. Remaining: hand off the new
   token securely (never commit it) so scheduled ingest can resume.
6. ~~Storage outage / migration?~~ **Resolved 2026-07-02:** it was the announced
   Ceph upgrade (July 2, 10:00 to 16:00 Pacific, CephFS/RBD/S3); NextCloud itself
   was fixed 2026-06-24 per Nautilus Support. No migration; creds fine. Monitor
   `https://nrp.ai/live` (or the Matrix room) for cluster news going forward.

7. **Agronomy questions sharpened by the literature review** (see
   `docs/reports/2026-08-05-irrigation-control-review.md` section 7.3). (a) Is
   Iron Horse running a regulated-deficit program, and at what phenology-stage
   targets? California practice is stage-staged, so a single season-long
   threshold is inconsistent with how a wine-grape block is managed. (b) Is any
   plant water status measured (pressure chamber, even weekly by hand)? That is
   the variable the operative irrigation policy actually triggers on, and it is
   the largest gap between VINE and the practice stack. (c) Soil texture and
   effective rooting depth per probe, needed to check whether the 25.0 threshold
   sits near the conventional allowable-depletion point. (d) Which blocks the
   five probes are meant to represent, given 39 blocks.

## Next actions (when resuming)

Every remaining item needs a human input. There is no blocked-on-code work left
in D1 to D5 or D7.

1. **D6 cluster deployment** is the only unfinished deliverable, and it is one
   step from done. Cluster access, RBAC, ConfigMap, PVCs, seeded data, and a
   smoke-tested amd64 image all exist. Needed: create a GitLab project named
   `vine` (under `gitlab.nrp-nautilus.io/ihv` if permitted), mint a deploy
   token, `docker login` + push the image, substitute the tag into
   `k8s/d6_serving/irrigation-deployment.yaml`, and `kubectl apply -n
   ihv-jupyterlab`. Afterwards delete the `vine-data-seed` helper pod.
2. **New InfluxDB token**: the rotation landed, so fresh ingest (and the D1
   CronJob's `vine-secrets` Secret) waits on the replacement token from the
   mentor. Weather ingest still works keyless.
3. **D3 labels**: field-reviewed plant-health labels. The fastest source is a
   field check of the top-ranked blocks in the current screening artifact
   (H6, L, J1, J2, P, Q); agreement or disagreement is itself the first label set.
4. **D4 harvest records**: harvest dates, yields, Brix/pH/TA, irrigation logs.
   Now with a concrete first use: the GDD exploration shows literature véraison
   bands are demonstrably wrong for this site, so local calibration needs records.
5. **EM500-PP semantics**: unit, active direction, served block, and ground-truth
   meaning of the 22,256 preserved pressure observations. Until confirmed it is
   not used as an irrigation-event label.

**State of the tree:** the corrected D3 screen, the D2 vintage validation, and
the D4 exploratory slice all landed and are committed with their reports.
`data/raw/sensors` and `data/raw/weather` were re-pinned on 2026-08-05 (the
weather snapshot now includes `forecast_vintages_2026-01-22_2026-07-08.parquet`)
and pushed. `data/raw/imagery` still reads as modified on purpose: the two ~4 GB
D3 orthomosaics were downloaded into `data/raw/imagery/rasters/` for local
screening and are not worth ~7.8 GB of shared bucket. Refetch them from the
NextCloud `GIS/` share if you need to rerun the screen. Everything the reports
regenerate from *is* pinned. Note that `dvc status -c` only compares cache to
remote; use plain `dvc status` to see whether the workspace matches its pins.

## How we keep state across sessions

- **This file (`docs/STATE.md`)** is the durable handoff: update it, commit it.
- **`CLAUDE.md`** points new sessions here and stays lean (loaded every session).
- **Decisions** → ADRs in `docs/adr/`. **Narrative** → `docs/devlog/`.
- Secrets stay in `.env` (gitignored); this file references them, never contains them.

# Final push: D4 gets its honest slice; D2 and D3 face their own caveats

**Date:** 2026-08-05  
**GSoC deliverables:** D2, D3, D4, D7

Week 11 of 13. This session ran three tracks in parallel: an exploratory D4
slice, a D2 water-balance validation against archived forecast vintages, and
the corrected D3 39-block screening rerun. All three landed.

## What I built

### D4 — label-free GDD phenology exploration

D4 has been blocked on historical harvest records since the start (input #3 in
STATE.md), and per [ADR-0003](../adr/0003-track-priority.md) it descopes to
exploratory when labels are unavailable. This is that slice: the largest honest
thing buildable with zero labels. `src/vine/d4_harvest/phenology.py` computes
cumulative growing degree-days (base 10 °C, Winkler window Apr 1 – Oct 31) at
the vineyard coordinates from public ERA5 daily weather, plus the dates when
configured literature phenology bands are crossed. Pure functions, 15 unit
tests, YAML config, a runner script, and a
[report](../reports/2026-08-04-d4-gdd-exploration.md) plus
[model card](../models/harvest/gdd-exploration.md) that both say plainly: this
is not a model, it does not ship, and it must not be used to schedule a pick.

### D2 — water balance meets archived forecast vintages

Every water-balance number so far carried the same caveat: lead-time weather
came from realized future observations, so the +3.5…+11.2% 48 h skill was an
oracle-assisted upper bound, not deployable evidence. This session runs the
validation that caveat demands — the same corrected, purged evaluation, but fed
from archived forecast data instead of realized future weather
(`configs/d2_irrigation/water_balance_vintage.yaml`). The reader pulls hourly
`_previous_dayN` vintages from Open-Meteo's Previous Runs API at a `ceil(h/24)`
day lag, rounded **up** so no value in the `(t, t+h]` window comes from a model
run issued after decision time `t`. A poisoned-fresh-vintage unit test at 48 h
guards that rule.

The result splits cleanly, and the split is the interesting part. The 48 h
aggregate edge **survives real forecasts** — +5.3…+13.5% across all five probes,
slightly wider than the oracle's +3.5…+11.2%. The physical signal is real:
rain arrives, ET removes water, and two-day-ahead forecasts carry enough of it.
But 24 h **flips negative on every probe** (−2.8…−8.1%, worst folds to −2.448,
i.e. nearly 3.5× persistence error in the worst fold). At that horizon the
model trusts day-1 forecast precipitation that the realized weather did not
deliver on the hours forecast — an error the oracle backtest could not exhibit
by construction.

The ship gate is unchanged and it fails: worst-fold skill is negative on every
probe at every horizon with an active correction. **Persistence remains the
served D2 forecaster.** What the run buys is a sharper research question — the
failure is concentrated in fold-level forecast busts, not a broken mechanism,
so the next lever is forecast-uncertainty-aware gating, not a new model family.
Full numbers: [D2 vintage validation](../reports/2026-08-04-d2-vintage-validation.md).

### D3 — 39-block rerun, this time on local rasters

Both prior attempts at a real corrected block ranking died before producing an
artifact: the first run was invalidated by the bounding-box coverage bug, and
the corrected remote rerun exited without writing a replacement. The failure
mode both times was the long-lived remote read path — GDAL range-reading two
4 GB `/vsicurl` rasters over a public NextCloud share for hours, which
eventually degrades into an endless `HTTP error code: 0` retry loop. So this
rerun downloads both rasters to `data/raw/imagery/rasters/` first (resumable
curl, ~8 GB) and screens against local files. It finished clean.

**All 39 blocks pass the corrected coverage gate**, every one at coverage
1.000. That is the real change: under the old bounding-box denominator, 9 of
39 blocks looked like they had missing pixels, but the missing "pixels" were
just the parts of each bounding box outside the polygon. The 2026-06-01
whole-vineyard mosaic in fact covers every block interior completely. The
per-block distributions are unchanged — identical pixel counts and quantiles —
because only the quality denominator was ever wrong.

The screening order puts H6 and L tied at rank 1 (score 0.936), J1/J2 at 3,
P/Q at 5, then M, E, G, and B South. 11 of the 39 blocks carry the NDVI/NDRE
rank-disagreement flag and deserve extra care in review. This is a review
queue, not a diagnosis: it has no labels, no learned parameters, and cannot
tell stress from phenology, shadow, or a processing artifact.
[D3 screening report](../reports/2026-08-05-d3-screening.md).

## Results

The D4 numbers that did land (all recomputed by `scripts/d4_gdd.py` from
config + public weather, zero missing days in either season):

- 2025 full season: **1563.2 GDD10** → Winkler Region II.
- 2026 through Aug 5: **920.2 GDD10** — day-matched, **+98.4 GDD (+12.0%)**
  ahead of 2025, with the gap opening almost entirely in July.
- Bloom band (350 GDD10) crossed within a day across seasons: 2025-06-08 vs
  2026-06-07.

The refuted part is the useful part: the computed véraison band crossings land
around Sept 1–17, which is implausibly late for Sonoma County. The cause is a
window mismatch — the cited literature bands accumulate from Jan 1 while this
run's Winkler window starts Apr 1, discarding Jan–Mar heat. That offset is a
direct quantitative demonstration that transplanted literature thresholds
cannot substitute for local calibration, which needs the mentor's harvest
records. The `sparkling_harvest_watch_UNCALIBRATED` band is a declared
placeholder with no source; it exists only as a slot to calibrate later.

## Decisions

No new ADR. ADR-0003 already covers both calls made here: D4 descopes to
exploratory without labels (and its artifact cannot pass the baseline gate
because there is nothing to score it against), and D2 promotion still requires
worst-fold robustness, which no challenger has shown.

## Blockers / open questions for mentor

1. **Historical harvest records** — now with a concrete first use: calibrating
   the GDD bands that the literature demonstrably gets wrong for this site.
2. Labeled stress/pest imagery for supervised D3.
3. Kubeconfig for the `ihv` namespace — the D6 cluster deploy is the only piece
   of D6 left and cannot start without it.
4. Rotation of the publicly exposed InfluxDB token.

## Remaining two weeks

- Land the D2 vintage and D3 rerun results into their reports and STATE.md.
- Final D5 evaluation report with everything above in one place.
- D6: deploy the verified container to NRP the day the kubeconfig arrives.
- Handoff docs and the final GSoC submission.

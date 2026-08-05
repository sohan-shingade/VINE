# D4 report: label-free GDD phenology exploration (2025 vs 2026)

**Deliverable:** D4 harvest timing · **Date:** 2026-08-05 · **Status:** exploratory
climate context. **Not a model and not a harvest predictor.**

D4 is blocked on historical harvest dates, yields, and Brix/pH/TA
(`docs/STATE.md` input #3). Per [ADR-0003](../adr/0003-track-priority.md), D4
descopes to exploratory when labels are unavailable. This is that exploratory
slice: what can be computed with zero labels.

## What was computed

Cumulative growing degree-days (GDD, base 10 °C, no upper cap) at the vineyard
coordinates (38.457, −122.896), accumulated over the Winkler convention window
Apr 1 to Oct 31, plus the date each configured literature phenology band was
crossed.

- Code: `src/vine/d4_harvest/phenology.py` (pure functions; 15 unit tests in
  `tests/d4_harvest/test_phenology.py`)
- Config: `configs/d4_harvest/gdd_exploration.yaml`
- Runner: `scripts/d4_gdd.py`
- Weather: `vine.d1_pipeline.fetch_historical` → Open-Meteo archive (ERA5),
  public, no key. Live pull on 2026-08-05: 492 daily rows, 2025-04-01 .. 2026-08-05.
- Artifacts: `data/processed/d4_gdd_trajectories.csv` (341 season-days),
  `data/processed/d4_gdd_crossings.csv` (10 rows)

Method: daily GDD = max(mean(Tmax, Tmin) − 10 °C, 0), summed over the season.
This is the Winkler heat-summation index (Amerine & Winkler 1944). Base and
optional upper cap are config knobs; the classic (uncapped) variant is used
here.

## Season trajectories

| Season | Days observed | Missing days | GDD total (°C-days) | Winkler class |
|---|---|---|---|---|
| 2025 (Apr 1 to Oct 31, complete) | 214 | 0 | **1563.2** | Region II |
| 2026 (Apr 1 to Aug 5, in season) | 127 | 0 | **920.2** | n/a (partial season) |

Day-matched, 2026 is running warmer than 2025:

| Checkpoint | 2025 cumulative | 2026 cumulative | Δ |
|---|---|---|---|
| Jun 30 | 538.6 | 549.5 | +10.9 |
| Jul 31 | 766.8 | 860.4 | +93.6 |
| Aug 5 | 821.8 | 920.2 | **+98.4 (+12.0%)** |

Mean daily Tmax/Tmin over Apr 1 to Aug 5: 22.88 / 10.02 °C in 2025 vs
23.64 / 10.85 °C in 2026. The 2026 gap opens almost entirely in July.

Neither season has a missing weather day (`season_missing_days = 0`), so both
curves are complete rather than lower bounds. Gaps would be flagged, never
imputed: a missing day yields NaN for that day's contribution and increments
`missing_days_to_date`, and any crossing after a gap is marked `complete=False`.

## Band crossings

Bands are configurable literature reference values, not local calibration.
Sources are in the module docstring: Chardonnay flowering ≈350 GDD10 (Van Leeuwen
et al., "Heat requirements for grapevine varieties", IVES OpenScience; Bavaresco
et al. 2019, BIO Web Conf. 12, 01010); véraison 908 to 1250 GDD10 across
cultivars, Chardonnay mid-véraison 1165 GDD10 (same sources). The configured
véraison-start threshold is **1100**, not the literature floor of 908: 908 is
the cross-cultivar minimum, while Chardonnay's own mid-véraison sits at
1165, so 1100 brackets that mid-point from below. This is a judgement call,
not a cited value, and it moves the crossing date. The headline "too late"
finding is therefore conservative, since the lower 908 threshold would place
the crossing *earlier* and closer to plausible, while the
Jan-1-vs-Apr-1 accumulation mismatch below remains the dominant error.

| Season | Band | Threshold | Crossed | Day of season |
|---|---|---|---|---|
| 2025 | bloom | 350 | 2025-06-08 | 69 |
| 2025 | véraison (start) | 1100 | 2025-09-01 | 154 |
| 2025 | véraison (end) | 1250 | 2025-09-17 | 170 |
| 2025 | sparkling watch (UNCALIBRATED, start) | 1250 | 2025-09-17 | 170 |
| 2025 | sparkling watch (UNCALIBRATED, end) | 1500 | 2025-10-19 | 202 |
| 2026 | bloom | 350 | 2026-06-07 | 68 |
| 2026 | véraison and later bands | 1100+ | not reached as of Aug 5 | — |

**The véraison dates above are almost certainly too late, and that is the
useful finding.** Both cited papers accumulate from **Jan 1**; this run
accumulates from **Apr 1**, discarding January through March heat, so every
threshold is reached later here than in the source literature. Sonoma County
véraison typically falls in late July or August, not September 1. The offset is
direct quantitative evidence that transplanted literature thresholds cannot
substitute for local calibration, which needs the mentor's records.

The `sparkling_harvest_watch_UNCALIBRATED` band (1250 to 1500 GDD10) is a
declared placeholder and not evidence. Iron Horse picks Chardonnay/Pinot Noir
early for sparkling base wine (~17 to 21 °Brix), well before still-wine
maturity, and no peer-reviewed °C-GDD threshold for a sparkling pick was found.
It exists only so the crossing table has a slot to calibrate once real harvest
dates arrive. Do not schedule anything from it.

## What this is NOT

This is **not a harvest-timing model and must not be used to schedule a pick.**
It has no labels, no learned parameters, no training, no held-out evaluation, and
therefore no measured skill against any baseline. It cannot pass the ADR-0003
baseline gate because there is nothing to score it against. It does not predict
harvest date, readiness, Brix, yield, or days-to-harvest, and it says nothing
per block: GDD here is one gridded weather point for the whole vineyard, so
block-level variation, aspect, soil, canopy management, crop load, rootstock,
and clone are all invisible to it. The band-crossing dates are literature
thresholds applied to local weather, not observed phenology at Iron Horse.
Nobody has confirmed that any vine at IHV did anything on those dates.
Validation is impossible without mentor-provided records.

## What unblocks full D4

1. **Historical harvest records** (mentor input #3): per-block harvest dates,
   ideally several vintages, with yield and Brix/pH/TA at pick. With ≥3 seasons
   the GDD-at-harvest per block becomes a real, testable local threshold, and
   `d4_harvest/baselines.py` ("same date as last year") becomes the baseline to
   beat under the D5 walk-forward harness.
2. **In-season maturity sampling** (Brix/TA time series): turns harvest timing
   into a trajectory-forecasting problem rather than a single sparse label.
3. **Growing-season imagery cadence:** NDVI/NDRE trend per block would add the
   spatial dimension GDD lacks. Flights currently skew winter/dormant
   (`docs/STATE.md`).

Until (1) exists, D4 stays exploratory and this page is its full extent.

## Reproduce

```bash
uv run python scripts/d4_gdd.py configs/d4_harvest/gdd_exploration.yaml
```

Weather is fetched live from the public Open-Meteo archive (no key), or read
from a local snapshot if `snapshot_csv` is set in the config. The archive is
ERA5 reanalysis at a grid cell, not an on-site station: it is regionally
accurate but not a vineyard-microclimate measurement.

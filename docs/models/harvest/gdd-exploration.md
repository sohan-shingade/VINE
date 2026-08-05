# Model card: harvest/gdd-exploration

> **This is not a model and it does not ship.** It has no learned parameters,
> no labels, no training, and no held-out evaluation. There is nothing to score
> it against, so it cannot pass the ADR-0003 baseline gate and does not claim to.
> It exists as exploratory climate context while D4's real inputs (historical
> harvest records) remain unavailable. This card documents it so nobody mistakes
> it for a harvest predictor.

## Model details

- **Track / deliverable:** Harvest timing (D4), descoped to exploratory per [ADR-0003](../../adr/0003-track-priority.md)
- **Architecture:** None. Deterministic arithmetic: daily GDD = max(mean(Tmax, Tmin) − 10 °C, 0), summed over the Winkler window Apr 1 to Oct 31 (Amerine & Winkler 1944), plus dates when configured literature phenology bands are crossed.
- **Version / run:** No MLflow run, because nothing is trained. Reproduced by `scripts/d4_gdd.py` from config + public weather.
- **Config:** `configs/d4_harvest/gdd_exploration.yaml`
- **Author & date:** Sohan Shingade, 2026-08-05

## Intended use

- **Primary use:** Season-to-season heat-accumulation context for Iron Horse Vineyard (e.g. "2026 is running +12.0% ahead of 2025 day-matched as of Aug 5"), and a concrete demonstration of why literature phenology thresholds need local calibration.
- **Users:** VINE researchers and the mentor, as context for future D4 work.
- **Out of scope:** Scheduling a pick, predicting harvest date, readiness, Brix, yield, or days-to-harvest; any per-block statement; any operational decision.

## Training data

None. No labels and no learned parameters. Input is daily Tmax/Tmin from the public Open-Meteo archive (ERA5 reanalysis) at the vineyard coordinates (38.457, −122.896), pulled live on 2026-08-05 (492 daily rows, 2025-04-01 through 2026-08-05; zero missing days in either season). ERA5 is a grid cell, not an on-site station. Missing days would be flagged, never imputed; crossings after a gap are marked incomplete.

## Evaluation

No skill evaluation is possible without harvest or phenology labels; none is claimed. What is verified:

- **Engineering checks:** 15 unit tests in `tests/d4_harvest/test_phenology.py` (accumulation arithmetic, gap flagging, band-crossing logic).
- **Computed outputs** (from `docs/reports/2026-08-04-d4-gdd-exploration.md`): 2025 season total 1563.2 GDD10 → Winkler Region II; 2026 at 920.2 GDD10 through Aug 5, +98.4 GDD (+12.0%) ahead of 2025 day-matched; bloom band (350 GDD10) crossed 2025-06-08 vs 2026-06-07.
- **Negative finding, kept deliberately:** the computed véraison band crossings (around Sept 1 to 17, 2025) are almost certainly too late, because the cited literature bands accumulate from Jan 1 while this run's Winkler window starts Apr 1. The offset quantitatively demonstrates that transplanted literature thresholds cannot substitute for local calibration.

## Limitations & caveats

- One gridded weather point for the whole vineyard: block-level variation, aspect, soil, canopy management, crop load, rootstock, and clone are all invisible.
- Band-crossing dates are literature thresholds applied to local weather, not observed phenology. Nobody has confirmed that any vine at IHV did anything on those dates.
- The `sparkling_harvest_watch_UNCALIBRATED` band (1250 to 1500 GDD10) is a declared placeholder with no peer-reviewed source; it exists only as a slot to calibrate once real harvest dates arrive.
- Everything here becomes obsolete the day mentor-provided harvest records exist; at ≥3 seasons of per-block pick dates, GDD-at-harvest becomes a real testable threshold under the D5 harness.

## Ethical & operational considerations

The main risk is misuse: a table of dates looks like a forecast. It is not one, and this card, the report, and the module docstring all say so. No irrigation, harvest, or vineyard operation should be planned from these numbers.

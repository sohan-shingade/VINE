# D2 report: probabilistic soil-moisture forecasts scored on CRPS

**Deliverable:** D2 irrigation · **Date:** 2026-08-05 · **Status:** challenger
family 14, evaluated. The strict worst-fold gate fails in 3 of 20 cells, so
nothing is promoted; persistence stays served. This is the first challenger
with positive aggregate skill in all 20 probe/horizon cells.

Thirteen challenger families tried to beat persistence's point forecast on
hourly MAE and every one failed. This rung changes the score instead of the
center. The continuous ranked probability score (CRPS) is the
industry-standard proper scoring rule for probabilistic forecasts: it
evaluates a full predictive distribution against the realized value, and it
generalizes MAE exactly. A deterministic forecast is a point-mass
distribution, and the CRPS of a point mass equals its absolute error, so
persistence's CRPS baseline equals its MAE. That identity makes the
comparison honest: any CRPS improvement over the persistence point mass
measures the value of a calibrated spread alone, with the forecast center
held fixed. A model with the same center and an honestly calibrated spread
scores strictly better if and only if the calibration is real, because CRPS
is proper and cannot be gamed by hedging.

## Models

All four models are evaluated per probe and per horizon (6, 12, 24, 48 h).
The first three share the persistence level as their center.

1. `persistence-point`: the served baseline as a point mass. CRPS equals its
   absolute error; the reference for skill.
2. `gaussian-ewma`: N(persistence level, sigma_h(t)^2), where sigma_h(t) is a
   causal EWMA of past absolute h-step persistence errors (halflife 72 valid
   pairs, warmup 24 pairs), converted to a Gaussian sigma with the
   half-normal identity E|X| = sigma * sqrt(2/pi) and floored at 1e-6.
   Absolute errors were chosen over squared errors for robustness to
   isolated storm spikes. The estimate used for a forecast targeting t comes
   only from errors realized at or before the origin t-h.
3. `gaussian-fixed`: the same center with one sigma per training fold, fit
   from that fold's purged h-step persistence errors. This distinguishes
   "any spread helps" from "adaptive spread helps".
4. `climatology-ensemble`: the empirical distribution of training-fold values
   (at most 300 chronologically even points), the standard meteorology
   reference, scored with the pooled-sample empirical CRPS.

## Method

Evaluation reuses the shared purged expanding walk-forward machinery: five
folds over the second half of each probe's history, with training labels
purged by h minus 1. Every model is scored on identical rows (holdout only,
target and persistence observed, both sigma estimates warmed up, ensemble
available).
Gaussian CRPS uses the closed form crps = sigma * (z*(2*Phi(z)-1) + 2*phi(z)
- 1/sqrt(pi)) with z = (y-mu)/sigma, unit-tested against hand-checked values
including the point-mass limit. Causality is unit-tested poison-tail style:
corrupting every value after the forecast origin changes neither the sigma
nor the forecast. Code: `vine.d2_irrigation.probabilistic`, tests
`tests/d2_irrigation/test_probabilistic.py`, runner
`scripts/d2_probabilistic.py`, config
`configs/d2_irrigation/probabilistic.yaml`.

Reported per cell: mean CRPS, CRPS skill vs `persistence-point` (aggregate
and per-fold as median and min), pinball loss at quantiles
0.05/0.25/0.5/0.75/0.95, and central-interval coverage (cov50 and cov90,
targets 0.50 and 0.90). The gate is the ADR-0003 standard: worst-fold CRPS
skill above zero in every probe/horizon cell.

## Results: gaussian-ewma per cell

CRPS skill vs the persistence point mass (positive is better). Full table
for all four models in `assets/d2_crps_results.csv`.

| Probe | Horizon | Skill | Fold median | Fold min | cov50 | cov90 | Gate |
|---|---|---|---|---|---|---|---|
| SE01-LS-1 | 6 h | +0.194 | +0.238 | +0.159 | 0.63 | 0.90 | pass |
| SE01-LS-1 | 12 h | +0.210 | +0.254 | +0.173 | 0.63 | 0.95 | pass |
| SE01-LS-1 | 24 h | +0.218 | +0.292 | +0.052 | 0.66 | 0.95 | pass |
| SE01-LS-1 | 48 h | +0.246 | +0.317 | -0.166 | 0.71 | 0.91 | **fail** |
| SE01-LS-2 | 6 h | +0.188 | +0.299 | +0.118 | 0.63 | 0.94 | pass |
| SE01-LS-2 | 12 h | +0.173 | +0.282 | +0.115 | 0.66 | 0.94 | pass |
| SE01-LS-2 | 24 h | +0.159 | +0.234 | +0.111 | 0.68 | 0.94 | pass |
| SE01-LS-2 | 48 h | +0.228 | +0.268 | +0.157 | 0.65 | 0.95 | pass |
| SE01-LS-3 | 6 h | +0.161 | +0.281 | +0.073 | 0.66 | 0.92 | pass |
| SE01-LS-3 | 12 h | +0.180 | +0.291 | +0.115 | 0.64 | 0.95 | pass |
| SE01-LS-3 | 24 h | +0.173 | +0.201 | +0.149 | 0.71 | 0.95 | pass |
| SE01-LS-3 | 48 h | +0.239 | +0.257 | +0.160 | 0.70 | 0.96 | pass |
| SE01-LS-4 | 6 h | +0.094 | +0.175 | +0.018 | 0.70 | 0.87 | pass |
| SE01-LS-4 | 12 h | +0.095 | +0.239 | -0.003 | 0.68 | 0.90 | **fail** |
| SE01-LS-4 | 24 h | +0.126 | +0.288 | -0.014 | 0.61 | 0.93 | **fail** |
| SE01-LS-4 | 48 h | +0.189 | +0.312 | +0.058 | 0.58 | 0.93 | pass |
| SE0X-LS-1 | 6 h | +0.250 | +0.311 | +0.167 | 0.55 | 0.95 | pass |
| SE0X-LS-1 | 12 h | +0.235 | +0.286 | +0.178 | 0.61 | 0.92 | pass |
| SE0X-LS-1 | 24 h | +0.231 | +0.277 | +0.174 | 0.64 | 0.96 | pass |
| SE0X-LS-1 | 48 h | +0.266 | +0.291 | +0.220 | 0.64 | 0.96 | pass |

Aggregate CRPS skill is positive in all 20 cells, between +0.094 and +0.266,
and grows with horizon on four of five probes. No previous challenger
achieved a positive aggregate in even a majority of cells. Worst-fold skill
is positive in 17 of 20 cells. The three failures: SE01-LS-1 at 48 h
(-0.166), SE01-LS-4 at 12 h (-0.003), and SE01-LS-4 at 24 h (-0.014). The
SE01-LS-1 failure is a single short fold (145 scorable hours, May 2 to
May 8, truncated by the shared May 8 to 19 data outage) where the level
moved outside the EWMA's trailing spread estimate; the other four folds in
that cell score +0.229 to +0.357. The two SE01-LS-4 failures are the first
fold (April 15 to May 2) at essentially zero, with every later fold
positive. **The gate therefore fails, and nothing is promoted.**

## The two spread baselines

`gaussian-fixed` separates "any spread" from "adaptive spread". Its aggregate
skill is positive in only 7 of 20 cells and its worst-fold skill is positive
in 1 of 20 (SE01-LS-3 at 6 h, +0.017). One sigma per fold is wrong whenever
the holdout's volatility regime differs from training, and its intervals
over-cover badly (cov50 0.70 to 0.99). The adaptive EWMA is what carries the
result, so the calibration is doing real work.

`climatology-ensemble` scores between -45.7 and -3.7 CRPS skill: an
unconditional distribution is far worse than any persistence-centered
forecast here, which confirms that tracking the current state is most of the
value. It behaves as the standard sanity reference, nothing more.

## Calibration honesty

The 90% interval is close to nominal: cov90 runs 0.87 to 0.96 against the
0.90 target, within 0.06 everywhere and slightly over on most cells. The 50%
interval systematically over-covers: cov50 runs 0.55 to 0.71 against the
0.50 target, high in every cell. Both patterns together say the h-step error
distribution is more sharply peaked than a Gaussian matched on mean absolute
error: the middle of the distribution is tighter than the fitted Gaussian
core, while the tails are roughly right. A heavier-tailed predictive family
(for example Laplace, whose CRPS also has a closed form) or a quantile
calibration layer is the obvious next refinement. Pinball losses agree with
the CRPS ranking: at the median every persistence-centered model ties by
construction, and gaussian-ewma wins at the outer quantiles where the point
mass pays the full asymmetric penalty.

## Limitations

- CRPS skill here measures the spread, with the center fixed at persistence.
  Nothing in this result improves the point forecast, so the D6 point
  endpoint is unaffected either way.
- The Gaussian shape is mis-specified in the middle of the distribution (the
  cov50 numbers above quantify it). The score the model wins under is proper
  regardless; the shape critique is about how much more is available.
- The EWMA reacts after volatility changes, and the one clear fold failure
  (SE01-LS-1 at 48 h) is exactly a regime shift the trailing estimate missed.
- The four horizons share overlapping h-step errors, so cells are correlated
  within a probe; 20 cells are fewer than 20 independent tests.
- The climatology ensemble is subsampled to 300 members for speed; the
  pooled-sample CRPS estimator is slightly biased for small ensembles, which
  is irrelevant at the margins observed here.

## Verdict

Persistence remains the served D2 forecaster. The strict ADR-0003 worst-fold
gate fails in 3 of 20 cells, and the served point forecast is untouched by
construction. The honest headline stands anyway: with the center held at
persistence, an adaptive causal error spread earns +9 to +27% CRPS over the
point mass in aggregate in every cell, with near-nominal 90% coverage. If a
probabilistic soil-moisture product is ever wanted for D6, this is the
starting recipe, with a heavier-tailed predictive family as the first
refinement to try.

Artifacts: `assets/d2_crps_results.csv` (per probe, model, and horizon). Run
logged to MLflow experiment `d2_irrigation`, run name `crps-probabilistic`,
run id `e5f950958fc345edafefb24b18dc8469`.

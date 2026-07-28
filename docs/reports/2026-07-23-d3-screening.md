# D3 report: label-free NDVI/NDRE block screening (superseded run)

> **Superseded evidence — do not use the coverage split or block ranks below.**
> An adversarial review found that the original coverage denominator counted each
> polygon window's bounding box and that rejected rows influenced accepted-block
> percentiles. Corrected polygon-interior coverage and accepted-only ranking logic
> pass regression tests. An authenticated range-backed rerun was externally terminated
> before writing a replacement artifact, so no current real-data block rank is claimed.
> This page is retained only as an audit trail.

**Deliverable:** D3 plant-health CV · **Date:** 2026-07-23 · **Status:** superseded
engineering artifact, not a supervised model

This report is generated offline by `scripts/generate_reports.py` from
[`assets/d3_screening_result.csv`](assets/d3_screening_result.csv), the retained original
result artifact from the real 2026-06-01 raster screen. Artifact SHA-256:
`6bd23b3f225043b1da789e068fb55f2facf3e2ea3e360f1f7d17e336a9764902`. The generator does **not** open or download the source rasters.

## What this was

A same-acquisition, label-free ranking of 39 vineyard blocks using NDVI/NDRE distribution
summaries. It had no learned parameters or ground truth. Its numerical output is now superseded
and must not be used to prioritize field review, diagnose stress, disease, or pests.

## Reproduction boundary

- D3 source rasters are multi-gigabyte remote files and are deliberately excluded from this
  offline report build.
- The retained artifact contains the original zonal distributions, coverage flags, and rankings.
  The tables and figures below are deterministically regenerated only to preserve the audit trail.
- Corrected raster statistics cannot be reconstructed from this artifact. The configured screen
  must finish against the rasters before this report can make a current block-level claim.
- The screening configuration is `configs/d3_vision/stress_screening.yaml`.

## Superseded coverage gate

The original run reported 39 blocks: **30 passed** its invalid coverage
calculation and **9 failed**. These counts are retained for audit only and are not current
evidence.

![Superseded per-block raster coverage](assets/d3_coverage.png)

## Superseded screening candidates

![Superseded top 15 screening candidates](assets/d3_top_ranked.png)

The original first four rows were H6, L, J1, J2. Do not use this ordering for field prioritization.
8 of 30 originally ranked blocks had the configured NDVI/NDRE rank
disagreement flag.

| block_id | rank | score | ndvi_coverage | ndre_coverage | ndvi_q50 | ndre_q50 | disagreement_flag |
|---|---|---|---|---|---|---|---|
| H6 | 1 | 0.936 | 0.523 | 0.523 | 0.328 | 0.127 | False |
| L | 1 | 0.936 | 0.565 | 0.565 | 0.363 | 0.106 | False |
| J1 | 3 | 0.917 | 0.750 | 0.750 | 0.365 | 0.111 | False |
| J2 | 3 | 0.917 | 0.715 | 0.715 | 0.365 | 0.100 | False |
| P | 5 | 0.904 | 0.623 | 0.623 | 0.361 | 0.129 | False |
| Q | 5 | 0.904 | 0.529 | 0.529 | 0.327 | 0.148 | False |
| M | 7 | 0.853 | 0.609 | 0.609 | 0.355 | 0.147 | False |
| E | 8 | 0.840 | 0.582 | 0.582 | 0.415 | 0.124 | False |
| G | 9 | 0.827 | 0.613 | 0.613 | 0.452 | 0.118 | False |
| B South | 10 | 0.801 | 0.686 | 0.686 | 0.426 | 0.140 | False |

The complete superseded output is
[`assets/d3_full_ranked.csv`](assets/d3_full_ranked.csv).

## Originally excluded blocks

Blank rank/score values reflected the original invalid coverage calculation, not low concern or
healthy vegetation.

| block_id | ndvi_count | ndvi_coverage | ndre_count | ndre_coverage |
|---|---|---|---|---|
| Cc | 6,774,087 | 0.180 | 6,774,087 | 0.180 |
| Cb | 8,681,699 | 0.189 | 8,681,699 | 0.189 |
| Ca | 12,573,890 | 0.262 | 12,573,890 | 0.262 |
| Triangle A | 4,243,110 | 0.357 | 4,243,110 | 0.357 |
| Cd | 6,654,807 | 0.398 | 6,654,807 | 0.398 |
| Ce | 8,425,366 | 0.402 | 8,425,366 | 0.402 |
| Train Barn | 6,247,847 | 0.427 | 6,247,847 | 0.427 |
| H1 | 5,843,170 | 0.472 | 5,843,170 | 0.472 |
| H4 | 3,497,423 | 0.477 | 3,497,423 | 0.477 |

Full superseded machine-readable detail is in
[`assets/d3_low_coverage.csv`](assets/d3_low_coverage.csv).

## Limits

- All block-level numbers and ranks on this page are superseded.
- Low indices can reflect phenology, background soil, shadows, pruning, irrigation, or
  processing artifacts. They are not disease labels.
- Scores are within-acquisition percentiles for 2026-06-01 and should not be compared directly
  with another date without matched footprints and seasonal controls.
- Thresholds and weights are screening choices, not vineyard-validated decision boundaries.
- No labeled stress/pest imagery is available, so no supervised accuracy is reported.
- **D4 harvest timing is not evaluated.** This artifact has no harvest-readiness, yield, or
  maturity ground truth.

## Next step

Complete a bounded, restartable authenticated raster run with the corrected implementation,
replace the retained artifact, and regenerate this report before field-review priorities are named.

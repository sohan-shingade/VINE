# Model card: plant-health/stress-screening

## Model details

- **Track / deliverable:** Plant health (D3)
- **Architecture:** Label-free, same-acquisition per-block NDVI/NDRE distribution ranking; no neural network and no biological classifier.
- **Version / run:** Corrected implementation verified on regression fixtures; no authoritative corrected real-data run artifact yet.
- **Config:** `configs/d3_vision/stress_screening.yaml`
- **Author & date:** Sohan Shingade, 2026-07-23

## Intended use

- **Primary use:** Rank vineyard blocks for human field inspection using low vegetation-index tails and medians.
- **Users:** Vineyard operators and VINE researchers.
- **Out of scope:** Diagnosing disease or pests, prescribing treatment, comparing unmatched seasons as causal change, or replacing agronomic inspection.

## Training data

No labels and no learned parameters are used. The implementation reads pre-computed NDVI and NDRE orthomosaic layers windowed by the 39 vineyard-block polygons from `IHV-2026-05-26.kmz`. The first configured acquisition is the whole-vineyard 2026-06-01 Pix4DFields export.

## Evaluation

- **Metrics:** Deterministic known-order synthetic fixtures, valid-pixel coverage/count, NDVI/NDRE rank disagreement, and ranking sensitivity.
- **Protocol:** Blocks are normalized and ranked only within a comparable acquisition. Low-coverage blocks are flagged and excluded from ranking.
- **Verified engineering checks:** Synthetic low-tail ordering, ties, missing coverage, disagreement flags, windowed raster summaries, and remote HTTP byte-range support pass.
- **Real-data coverage/result:** The original 39-block range-backed run is superseded: an adversarial review showed its coverage denominator used polygon bounding boxes, which unfairly rejected irregular blocks, and rejected rows still influenced accepted-block percentiles. Corrected polygon-interior coverage and accepted-only ranking logic pass regression tests. An authenticated corrected rerun was externally terminated before writing a replacement artifact, so no current block ranking is claimed.

## Limitations & caveats

- Low NDVI/NDRE can reflect phenology, soil/background, shadows, pruning, irrigation, calibration, or processing—not necessarily plant stress.
- August 2025 H-block imagery and June 2026 whole-vineyard imagery differ by season, year, and coverage. Temporal deltas are exploratory and confounded unless restricted to matched footprints/acquisition conditions.
- Thresholds and index weights are screening choices, not learned or vineyard-validated disease boundaries.
- No labeled stress/pest imagery is currently available; supervised accuracy must not be claimed.

## Ethical & operational considerations

The ranking should prioritize inspection, not stigmatize blocks or trigger autonomous treatment. Operators should verify high-concern candidates in the field and consider acquisition quality before acting. Large rasters are read windowed/range-backed to avoid unnecessary data transfer and resource use.

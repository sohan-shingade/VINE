# Model card: irrigation/persistence

## Model details

- **Track / deliverable:** Irrigation forecasting (D2)
- **Architecture:** Naive persistence: every 6/12/24/48 h forecast equals the latest valid soil-moisture reading; a fixed threshold recommends irrigation below 25.0.
- **Version / run:** Decision evidence is reproduced from YAML configs and DVC snapshots; historical exploratory runs also live in MLflow experiment `d2_irrigation`.
- **Config:** `configs/d2_irrigation/naive.yaml`; local serving config `configs/d6_serving/irrigation.yaml`
- **Author & date:** Sohan Shingade, 2026-07-23

## Intended use

- **Primary use:** Forecast near-term soil moisture and screen for irrigation need at instrumented Iron Horse Vineyard blocks.
- **Users:** Vineyard operators through the VINE API/dashboard, with grower review.
- **Out of scope:** Autonomous irrigation control; extrapolation to uninstrumented blocks or other vineyards; overriding grower judgment during frost, maintenance, sensor faults, or unusual field conditions.

## Training data

Persistence has no learned parameters. Evaluation used hourly sensor snapshots from five soil probes at Iron Horse Vineyard, covering approximately 2026-01-22 through 2026-07-08. The fifth probe (`SE0X-LS-1`) uses its first-depth raw LoRa soil channels after schema normalization.

Forecasts were evaluated at 6, 12, 24, and 48 hours. Missing readings and shared source outages were kept as gaps and excluded from scoring; they were never imputed. Weather was not required by persistence.

## Evaluation

- **Metrics:** Soil-moisture MAE/RMSE and irrigation-threshold precision/recall.
- **Protocol:** Expanding-window walk-forward evaluation on the chronological holdout half. Target-time-aligned learned models now purge the final `h-1` training labels at horizon `h`; persistence itself is a causal shift.
- **Baselines and challengers:** Persistence was the floor and remained the champion after per-sensor ridge, ridge with perfect-forecast features, ridge-delta, ARIMA, drydown trend, random forest, gradient boosting, pooled cross-sensor models, and a water-balance weather-correction experiment.
- **Observed performance:** On sensors whose holdouts cross the 25.0 threshold, persistence alert precision/recall is approximately 0.95–0.99. MAE increases from roughly 0.06–0.13 at 6 h to 0.29–0.52 at 48 h across the five probes.
- **Water-balance status:** Active experimental candidate, not removed. With realized future weather as an oracle upper bound, its corrected 48 h aggregate skill was positive on all five probes (+3.5% to +11.2%), but every probe had a negative worst fold and one operational recall comparison regressed slightly. It is promising enough for future archived-forecast/new-holdout evaluation, but has not cleared the production-promotion gate.

## Limitations & caveats

- Evaluation covers one vineyard and about 5.5 months, not multiple full seasons.
- Persistence cannot anticipate rain or irrigation events; it follows the latest state.
- The 25.0 threshold is an experimental decision rule and needs operator confirmation/calibration by block and sensor depth.
- Simultaneous source gaps affected all devices, including a long 2026-06-24 to 2026-07-08 outage.
- A stale reading can produce a numerically valid persistence forecast that is operationally unsafe. D6 therefore exposes freshness and suppresses recommendations when stale.
- Water balance used realized future weather, not archived forecast vintages; its reported gains are an upper bound, not deployable forecast evidence.

## Ethical & operational considerations

False negatives can contribute to crop stress; false positives waste water. Recommendations must remain human-in-the-loop. Operators should inspect sensor freshness, field conditions, weather forecasts, and irrigation records before acting. The service must not silently recommend from stale, missing, or invalid data.

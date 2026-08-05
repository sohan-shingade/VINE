# Model card: irrigation/persistence

## Model details

- **Track / deliverable:** Irrigation forecasting (D2)
- **Architecture:** Naive persistence: every 6/12/24/48 h forecast equals the latest valid soil-moisture reading; a fixed threshold recommends irrigation below 25.0.
- **Version / run:** Decision evidence is reproduced from YAML configs and DVC snapshots; historical exploratory runs also live in MLflow experiment `d2_irrigation`.
- **Config:** `configs/d2_irrigation/naive.yaml`; local serving config `configs/d6_serving/irrigation.yaml`
- **Author & date:** Sohan Shingade, 2026-08-05

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
- **Baselines and challengers:** Persistence was the floor and remained the champion after per-sensor ridge, ridge with perfect-forecast features, ridge-delta, ARIMA, drydown trend, random forest, gradient boosting, pooled cross-sensor models, a water-balance weather-correction experiment, a Prophet seasonal forecaster with a soil-temperature regressor, and an LSTM encoder-decoder sequence model.
- **Observed performance:** On sensors whose holdouts cross the 25.0 threshold, persistence alert precision/recall is approximately 0.95 to 0.99. MAE rises with horizon: roughly 0.06 to 0.13 at 6 h, and 0.29 to 0.52 at 48 h across the five probes.
- **Water-balance status:** Research, not promoted. It has now been evaluated on real archived forecast vintages as well as the realized-weather oracle. The 48 h aggregate edge survives the switch (+5.3% to +13.5% across five probes, against +3.5% to +11.2% under the oracle), but 24 h skill flips negative on every probe (−2.8% to −8.1%), and worst-fold skill is negative in every cell where the correction is ever active (four 6/12 h cells sit at exactly 0.000 because the correction never fires there). The promotion gate therefore fails. See the [vintage validation report](../../reports/2026-08-04-d2-vintage-validation.md).
- **Prophet and LSTM status:** Research, not promoted. These complete the proposal's named forecaster list under the same walk-forward protocol and `h-1` label purge, evaluated on SE01-LS-1 at 6, 12, 24, and 48 h. Prophet (daily and weekly seasonality, decision-time soil temperature as an external regressor, one fit per fold) posts aggregate skill vs persistence of −14.705 at 6 h, −8.380 at 12 h, −4.882 at 24 h, and −2.474 at 48 h, with worst-fold skill between −28.796 and −14.471. The LSTM encoder-decoder (72 h input window, hidden 128, 2 layers, trained 20 epochs on CPU, reduced from the sketch's 50 for runtime) posts −4.240 at 6 h, −6.034 at 12 h, −6.160 at 24 h, and −8.255 at 48 h, with worst-fold skill between −131.310 and −15.779; its 72 h window also shrinks the shared scorable set (n 998 to 956, against 1367 to 1335 for the classical runs) because windows crossing sensor gaps are never imputed. Neither model beats persistence at any horizon, so the ADR-0003 worst-fold gate is never reached. Full tables: `docs/reports/assets/d5_prophet_results.csv` and `docs/reports/assets/d5_lstm_results.csv`.

## Limitations & caveats

- Evaluation covers one vineyard and about 5.5 months, not multiple full seasons.
- Persistence cannot anticipate rain or irrigation events; it follows the latest state.
- The 25.0 threshold is an experimental decision rule and needs operator confirmation/calibration by block and sensor depth.
- Simultaneous source gaps affected all devices, including a long 2026-06-24 to 2026-07-08 outage.
- A stale reading can produce a numerically valid persistence forecast that is operationally unsafe. D6 therefore exposes freshness and suppresses recommendations when stale.
- Water balance has been tested on both realized future weather and archived forecast vintages; under real forecasts it loses to persistence at 24 h and fails the worst-fold gate wherever the correction is active. The remaining open question is per-fold robustness to forecast busts, not a new model family.

## Ethical & operational considerations

False negatives can contribute to crop stress; false positives waste water. Recommendations must remain human-in-the-loop. Operators should inspect sensor freshness, field conditions, weather forecasts, and irrigation records before acting. The service must not silently recommend from stale, missing, or invalid data.

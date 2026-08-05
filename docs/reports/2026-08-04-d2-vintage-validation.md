# D2 report: water balance on real archived forecast vintages

**Deliverable:** D2 irrigation · **Date:** 2026-08-04 · **Status:** validation
complete — **not promoted; persistence remains served**

The water-balance weather correction previously showed +3.5…+11.2% aggregate
48 h skill across all five soil probes, but that backtest fed the model
REALIZED future weather (a perfect-forecast oracle). This report replaces the
oracle with real archived forecasts as issued (Open-Meteo Previous Runs API)
and records the promotion decision against the ADR-0003 gate.

## Setup

- **Model + evaluation unchanged:** gated, Huber-robust, adaptively blended
  water balance (`configs/d2_irrigation/water_balance_vintage.yaml`), purged
  expanding walk-forward (5 folds, `h−1` training-label purge), 5 probes ×
  {6, 12, 24, 48} h, scored on identical rows as every baseline.
- **Weather source is the only variable:** `weather_source: oracle` fills the
  `et0_next_{h}h`/`precip_next_{h}h` drivers from realized weather;
  `weather_source: vintage` fills them from hourly `_previous_dayN` vintages.
  For horizon h the lag is `ceil(h/24)` days, rounded UP so every value in the
  `(t, t+h]` window comes from a model run issued at or before decision time t
  (never a fresher run than causally available; unit-tested, including a
  poisoned-fresh-vintage test at 48 h).
- **Coverage:** vintages fetched for the full sensor window 2026-01-22 →
  2026-07-08 (4,032 hourly rows, zero missing hours in either variable at
  either lag) and snapshotted to
  `data/raw/weather/forecast_vintages_2026-01-22_2026-07-08.parquet`
  (DVC-managed dir, not in git) so the run reproduces offline. Scorable rows
  (n ≈ 1,335–1,367 per horizon) are unchanged from the oracle run; the three
  shared sensor outages remain masked, never imputed.
- **Runs:** MLflow experiment `d2_irrigation`, runs
  `water-balance-all-sensors-vintage` and `water-balance-all-sensors-oracle`
  (2026-08-05). The fresh oracle run reproduces the 2026-07-23 numbers exactly.

## Results — aggregate skill vs persistence (%, MAE; positive = better)

| Probe | 6 h O | 6 h V | 12 h O | 12 h V | 24 h O | 24 h V | 48 h O | 48 h V |
|---|---|---|---|---|---|---|---|---|
| SE01-LS-1 | −0.4 | −0.3 | −0.6 | −1.2 | +1.2 | −8.1 | +9.4 | +10.6 |
| SE01-LS-2 | −0.4 | +0.1 | +0.6 | 0.0 | −4.8 | −5.2 | +9.6 | +5.3 |
| SE01-LS-3 | 0.0 | 0.0 | −0.2 | 0.0 | −5.4 | −5.6 | +7.3 | +7.9 |
| SE01-LS-4 | −0.3 | −0.7 | −0.2 | −1.1 | +2.7 | −4.0 | +11.2 | +5.4 |
| SE0X-LS-1 | −0.4 | −0.1 | +0.0 | −2.3 | +1.3 | −2.8 | +3.5 | +13.5 |

O = oracle (realized weather), V = vintage (real archived forecasts).

## Results — worst-fold skill vs persistence (the ship gate)

| Probe | 6 h O | 6 h V | 12 h O | 12 h V | 24 h O | 24 h V | 48 h O | 48 h V |
|---|---|---|---|---|---|---|---|---|
| SE01-LS-1 | −0.011 | −0.089 | −0.057 | −0.121 | −0.139 | **−2.448** | −0.341 | **−0.596** |
| SE01-LS-2 | −0.027 | 0.000 | 0.000 | 0.000 | −0.269 | **−1.223** | −0.323 | −0.440 |
| SE01-LS-3 | 0.000 | 0.000 | −0.022 | 0.000 | −0.206 | −0.555 | −0.148 | −0.0003 |
| SE01-LS-4 | −0.008 | −0.097 | −0.005 | −0.129 | 0.000 | **−1.102** | −0.097 | −0.181 |
| SE0X-LS-1 | −0.008 | −0.077 | −0.057 | −0.362 | −0.107 | −0.510 | −0.201 | −0.317 |

## Honest read

- The 48 h aggregate edge **survives real forecasts**: +5.3…+13.5% across all
  five probes (vs +3.5…+11.2% under the oracle). The physical signal — rain
  arrives, ET removes water — is real and 2-day-ahead forecasts carry enough
  of it. The zeros at 6–12 h are mostly the adaptive blend correctly
  collapsing to persistence.
- **Real forecasts make 24 h clearly worse than the oracle**: aggregate skill
  is negative on every probe (−2.8…−8.1%) and worst folds reach −1.1…−2.4
  (i.e. 2–3× persistence error in the worst fold). At this horizon the model
  trusts day-1 forecast precipitation that the realized weather did not
  deliver on the hours forecast.
- **The gate fails.** Worst-fold skill is negative on every probe at 48 h
  (−0.0003 on SE01-LS-3 at best, −0.60 on SE01-LS-1 at worst) and at every
  other horizon with any active correction. A model that loses to "do nothing"
  in one out of five recent-history folds on every probe cannot be trusted to
  schedule irrigation.
- Caveats: one 5.5-month season, 5 correlated probes sharing one weather grid
  cell, and the vintage lag is conservative (a 48 h decision uses a run up to
  2 days old; an operational system refreshing forecasts hourly would see
  slightly fresher runs than this backtest allows).

## Promotion decision

**Not promoted. Persistence remains the served D2 forecaster (ADR-0003), and
water balance stays research.** The ship gate is positive worst-fold skill vs
persistence on every probe; on real archived forecast vintages the model fails
it on all five probes at every horizon, and at 24 h it is worse than
persistence even in aggregate. The vintage run does establish two things: the
48 h aggregate improvement is not an oracle artifact, and the failure mode is
concentrated in fold-level forecast busts rather than a broken mechanism. That
makes the remaining research question sharp — per-fold robustness (e.g.
forecast-uncertainty-aware gating) — but until a variant clears the worst-fold
gate on vintage weather, the D6 service correctly keeps serving persistence +
threshold.

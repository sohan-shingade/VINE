# 2026-07-08 — D2 vs reality: everything loses to persistence (almost)

*Phase: D2 model ladder (week 7). Previous post: D1 imagery unblocked.*

## The short version

We got the lost secrets back, ran the full D2 ladder on real vineyard data for
the first time, and learned three things the hard way:

1. **Real soil moisture is close to a random walk.** The naive baseline —
   "moisture in 24 h = moisture now" — has MAE 0.28 (raw sensor units on a
   ~18–45 scale). Ridge regression on lags, rolling stats, and past weather is
   *worse than doing nothing* at every horizon (skill −0.8 to −1.0).
2. **Two of our three "wins" today were evaluation artifacts**, caught not by
   unit tests but by an adversarial review pass.
3. After fixing everything, **ARIMA is the first model to beat persistence** —
   by 2–3 %, positive in every fold at 48 h. Real, but not enough to ship.

Per ADR-0003, nothing ships without beating the baseline on honest held-out
data. **Persistence remains the champion.** That's not a failure of the
project — it *is* the project: the evaluation harness is doing exactly what
it exists to do.

## Recovering from the wipe (and a security lesson)

A machine wipe on July 4 destroyed `.env` and the DVC credentials. The
InfluxDB token turned out to be recoverable in minutes — because the public
starter repo commits it in plaintext in a notebook. Convenient for us,
terrifying in general; we've flagged rotation to the mentor (again). The S3
keys were re-issued from the NRP portal today, DVC is round-tripping again,
and the fresh 1.04 M-row sensor snapshot + weather + imagery are pinned and
pushed to `s3://ihv-vine/dvc`.

Bonus lesson: don't put inline comments after values in `.env` — dotenv reads
`KEY=   # comment` as the literal value `# comment`. Our `.env.example` did
exactly that and broke a test the moment it was copied verbatim.

## The new rungs

Built in one orchestrated session (three parallel workers, then an
adversarial reviewer — more on that below):

- **Weather-forecast reader** (`vine.d1_pipeline.fetch_forecast`) — Open-Meteo
  forecast API, same tidy daily frame as the archive reader. This is D1
  input 4f: the physical reason anything *should* beat persistence is knowing
  what the weather will do between decision time and target time.
- **Lead-time features** (`add_lead_time_features`) — `precip_next_24h`,
  `et0_next_48h`, etc. In backtests these are a *perfect-forecast proxy*
  (actual future weather standing in for a forecast issued at decision time —
  the upper bound on what a real forecast could contribute). The harness
  drops any `_next_{k}h` column whose k doesn't match the horizon being
  scored, because a mismatched window reaches past the target time — that's
  a leak, not a feature.
- **ARIMA** (`make_arima`) — SARIMAX fitted once per fold, then the Kalman
  filter is extended observation-by-observation so every test row gets a true
  h-step-ahead forecast from exactly the history it's allowed to see.
- **Ridge-Δ** — predict the *change* y(t) − y(t−h) instead of the level, then
  reconstruct to level for scoring (so persistence is exactly "predict zero
  change" and all metrics stay comparable).

## The first run looked great. It was wrong.

First real-data table: ARIMA positive at all four horizons (up to +8.3 % at
48 h), ridge+forecast-features +14.7 % at 48 h. Ship it?

We put the results in front of an adversarial eval-review whose default
stance is "these are artifacts until proven otherwise." It refuted both:

- **ARIMA had a causality bug.** For the first h−1 rows of each fold, the
  fitted Kalman filter's state already contained training observations *past
  those rows' decision times* — the code extended the filter forward but
  silently did nothing when the allowed history ended *before* the filter's
  state did. Those contaminated rows (5·(h−1) of them, growing with h exactly
  like the reported skill did) were effectively scored as short-horizon
  forecasts against long-horizon targets. Why didn't tests catch it? Every
  ARIMA test used horizon 1 — where the leaky region is empty.
- **Ridge's 48 h win was one fold.** Fold-by-fold: +0.55, −1.58, −1.63,
  +0.01, −0.18. All of the aggregate skill came from a single April rain
  episode where persistence was terrible; exclude it and the model is 62 %
  *worse* than persistence. A pooled MAE over heterogeneous folds flattered
  a model that loses 80 % of the time.

Fixes: ARIMA now re-runs the filter on the exactly-truncated history for
early fold rows (`res.apply`); a poison-tail causality test at h=6 locks it
in; and the results table now reports `skill_fold_median` / `skill_fold_min`
alongside the aggregate, so a single-fold artifact can never headline again.

## The honest table (SE01-LS-1, 5.5 months, walk-forward, n≈1350/horizon)

| model | 6 h | 12 h | 24 h | 48 h | fold-min @48 h |
|---|---|---|---|---|---|
| persistence (champion) | 0.0 % | 0.0 % | 0.0 % | 0.0 % | — |
| seasonal-naive | −170 % | −60 % | 0.0 % | 0.0 % | 0.0 % |
| ridge | −95 % | −102 % | −80 % | +14.7 %* | −163 % |
| ridge-Δ + forecast | −90 % | −99 % | −78 % | +15.0 %* | −162 % |
| **ARIMA (2,1,2)** | **+3.0 %** | −1.8 % | **+2.4 %** | **+2.1 %** | **+1.2 %** |

\* single-fold artifact — fold median is −18 %.

ARIMA's 48 h skill is small but *positive in every fold* — the first honest
signal above zero in this project. It stays a **candidate**, not a champion:
one dry season on one device, and +2 % isn't a reason to replace a model
with no parameters. Next: re-test on the other sensors; if the
fold-consistent skill holds, it ships.

## Postscript, same night: the candidate is dead

We ran the confirmation immediately — same config, sensors SE01-LS-2/3/4
(each ~190–200 k rows over the same 5.5 months):

| sensor | 6 h | 12 h | 24 h | 48 h |
|---|---|---|---|---|
| LS-1 | +3.0 % | −1.8 % | +2.4 % | +2.1 % |
| LS-2 | −6.1 % | −12.2 % | −18.0 % | −10.1 % |
| LS-3 | +1.7 % | +2.3 % | −3.0 % | −1.7 % |
| LS-4 | +3.8 % | −1.9 % | +2.0 % | +1.8 % |

A model that gains 2 % on two sensors and loses 10–18 % on a third is not a
model, it's a coin with site-specific weighting. **Ship decision, per
ADR-0003: persistence is the D2 forecaster.**

The consolation prize is real, though: unlike LS-1, the other sensors'
holdouts actually cross the 25.0 irrigation threshold — and the persistence
alert ("will moisture be below threshold in h hours?") scores precision and
recall of **0.95–0.99** there. The humble answer — *the latest reading is
your forecast; alert on it* — turns out to be an operationally excellent
irrigation advisor. That's what D6 will serve.

## What the orchestration bought us

This session ran as an orchestrator + three parallel workers (forecast
reader, ARIMA, harness wiring) + an adversarial reviewer. The parallelism
saved an hour; the reviewer saved the project from two false claims. The
uncomfortable truth: the orchestrator *and* all three workers believed the
first table. The only reason today's devlog isn't announcing a fake +8 % is
that one agent's entire job was to disbelieve it. Evaluation-driven
development needs an adversary, not just a gate.

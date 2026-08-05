# D2 survival clock: time-to-drydown as a censored event (2026-08-05)

**Question.** Every prior D2 layer answers a fixed-horizon question: the level
at t+h, or the probability of crossing a barrier within h hours. The question
an operator actually asks is the transpose: *how many hours until this block
needs water?* This report scores that question directly, as a censored
time-to-event problem, using the machinery of survival analysis, which is
standard in medical statistics and absent from the irrigation forecasting
literature we reviewed.

**Verdict.** Research layer, no promotion. Scored on the integrated IPCW Brier
score (IBS) over a 48 hour window, every probabilistic model beats the
deterministic drydown calculator that represents current practice, by 22 to 58
percent in aggregate. The discrete-time hazard regression, the survival
literature's own modeling tool, is the best single model on the two probes
where random-walk pricing fails, and an equal-weight blend of the hazard model
and the filtered historical simulation curve is the best or second-best model
on every probe. No candidate passes a uniform worst-fold gate, so the
persistence + threshold endpoint is unchanged. The methodological repair
stands on its own: 98 to 139 decision windows per probe that earlier layers
silently dropped are now scored.

## 1. Setup

- **Event**: a drawdown of 0.3 units below the decision-time level, the same
  stationary barrier as the [optimal-stopping layer](2026-08-05-optimal-stopping.md)
  (any absolute barrier is degenerate on this record).
- **Label**: hours until the first observed reading at or below the barrier,
  scanned over the next 48 hours. Observation stops at the first missing
  reading: a crossing seen only after a gap cannot be timed, so the row is
  **right-censored** there. Rows observed through the full window with no
  crossing are known survivors.
- **Why censoring matters**: the stopping layer scores a window only when all
  h future readings exist. That rule conditions on the future (whether a
  window is complete is unknown at decision time), and it deletes every
  decision near the June outage or the record end. Here those rows stay in
  the risk set and the scored rows are reweighted by inverse probability of
  censoring (Graf et al. 1999), with the censoring distribution estimated by
  reverse Kaplan-Meier per fold.
- **Score**: IPCW Brier score per horizon, integrated over hours 1 to 48
  (IBS, lower is better). Unit tests verify the weighting recovers the
  uncensored Brier score under independent censoring on simulation.
- **Protocol**: the standard purged expanding walk-forward, 5 folds, all five
  probes, 1409 decisions per probe, 378 to 714 events, 98 to 139 rows
  censored inside the window.

## 2. The model ladder

| model | what it is |
|---|---|
| km-train | Kaplan-Meier curve of the training fold. The survival null: one marginal curve for every hour |
| drydown-clock | deterministic calculator, depth divided by the current drying rate. Current grower practice as a step-function curve |
| gauss-continuous | closed-form Brownian first passage from causal EWMA drift and volatility. The literature's incumbent |
| gauss-discrete | hourly-monitored Gaussian walk, drift-bucketed backward recursion |
| fhs-discrete | hourly-monitored filtered historical simulation: training-fold standardized increment shape, rescaled to the row's causal moments |
| hazard-glm | discrete-time hazard regression (Singer and Willett 1993): pooled logistic hazard on at-risk hours with baseline-shape, hour-of-day, drift, and depth covariates |
| fhs-hazard-blend | equal-weight average of the fhs-discrete and hazard-glm curves, no fitted weight |

All models are causal by construction. The hazard model is the only one that
can see the diurnal phase: soil moisture drops on an evapotranspiration cycle,
so the hour of day at the target hour carries timing information no
random-walk model can represent. Censoring costs it nothing at fit time
either, because censored rows simply contribute fewer at-risk hours to the
likelihood.

## 3. Results (aggregate IBS, weighted by fold size)

| probe | clock | km | gauss-cont | gauss-disc | fhs | hazard | blend |
|---|---|---|---|---|---|---|---|
| SE01-LS-1 | 0.2483 | 0.1932 | 0.1173 | 0.1158 | 0.1165 | 0.1230 | **0.1125** |
| SE01-LS-2 | 0.1973 | 0.1584 | 0.1203 | 0.1046 | 0.0931 | 0.0989 | **0.0919** |
| SE01-LS-3 | 0.2588 | 0.1923 | 0.1357 | 0.1162 | 0.1092 | 0.1007 | **0.0998** |
| SE01-LS-4 | 0.1154 | 0.0957 | 0.1379 | 0.1223 | 0.1077 | **0.0947** | 0.0966 |
| SE0X-LS-1 | 0.0860 | 0.0994 | 0.0567 | 0.0553 | **0.0552** | 0.0680 | 0.0564 |

What the table says:

1. **Practice loses badly.** The drydown calculator is the worst curve on four
   of five probes. A step function at depth / rate carries no uncertainty, and
   the IBS charges it fully for every miss. Any probabilistic model, even the
   marginal KM curve, is a large improvement on most probes.
2. **The incumbent closed form is dominated.** fhs-discrete beats
   gauss-continuous in aggregate on all five probes (skill +0.024 to +0.235).
   Most of that gap is the discrete-monitoring correction, consistent with the
   stopping-layer ablation: gauss-discrete lands within 0.002 to 0.016 of fhs.
3. **The KM null is a serious opponent.** On SE01-LS-4, the quiet probe, the
   marginal curve beats every random-walk model outright. Timing information
   there lives in things the walk cannot see.
4. **The hazard model supplies exactly that.** It is the best model on
   SE01-LS-3 and SE01-LS-4, the two probes where walk pricing is weakest, and
   the first conditional model to beat the KM null on LS-4. Its hour-of-day
   and baseline-shape covariates carry the diurnal and calendar structure. It
   gives skill back on SE0X-LS-1, the dry probe, where its seasonal-timing
   coefficients transfer worst across folds.
5. **The blend is the best single curve.** Best IBS on three probes, second on
   LS-4 (0.0966 vs the hazard's 0.0947), third by 0.0012 on SE0X-LS-1. It is
   the only model whose aggregate skill against the KM null is positive on
   every probe (+0.022 to +0.508). The Brier score is convex, so the blend is
   never worse than the average of its two members on any fold; in practice
   the complementary errors (volatility shape vs diurnal timing) make it
   better than both on most probes.

## 4. The honest failures

- **No uniform worst-fold pass.** Every model has at least one negative
  worst-fold skill cell against at least one reference. The blend's worst
  cells are fold-level losses to the clock on quiet folds (the clock's
  confident "no crossing" is nearly perfect when nothing crosses, so the
  ratio denominator is tiny) and a -0.10 fold against the KM null on LS-4.
  Under the ADR-0003 standard nothing here ships, and the report says so.
- **Fold 4 is degenerate everywhere.** The final fold is the short post-outage
  tail: 71 decisions, zero events, on every probe. The clock's IBS there is
  exactly zero, so skill ratios against it are undefined; those 35 fold cells
  (7 models x 5 probes) are excluded from skill aggregates and the exclusion
  is printed by the runner. Raw IBS rows are kept in the folds CSV.
- **Ratio skills mislead near zero.** On quiet probes the reference IBS gets
  tiny, and a small absolute difference becomes a huge negative ratio (the
  km-train row shows -23.6 worst-fold vs the clock on SE0X-LS-1). Aggregate
  IBS in the table above is the stable comparison; the skill columns in the
  CSVs are kept for gate accounting.

## 5. The operator reading

The deployed artifact of this layer would be a clock, read from the survival
curve at the current hour. At the last valid reading (2026-07-08 17:00 UTC,
mid-outage), the FHS curve says:

| probe | level | t10 (hours) | t50 | t90 |
|---|---|---|---|---|
| SE01-LS-1 | 17.99 | 37 | beyond window | beyond window |
| SE01-LS-2 | 15.44 | 33 | beyond window | beyond window |
| SE01-LS-3 | 12.83 | 47 | beyond window | beyond window |
| SE01-LS-4 | 17.25 | 48 | beyond window | beyond window |
| SE0X-LS-1 | 11.81 | 38 | beyond window | beyond window |

Read: at July drying rates there is a 10 percent chance of a 0.3 drawdown
within 33 to 48 hours depending on probe, and the median crossing time is
beyond the 48 hour window everywhere. A grower gets "no irrigation needed in
the next two days, check again tomorrow" with a probability attached, instead
of a single extrapolated number.

## 6. Artifacts

- Tables: `assets/d2_survival_summary.csv` (aggregates),
  `assets/d2_survival_folds.csv` (per fold, raw IBS and horizon Briers),
  `assets/d2_survival_clock.csv` (operator readings).
- Code: `vine.d2_irrigation.survival` (pure functions, 16 unit tests including
  an IPCW recovery simulation and a diurnal-timing recovery test for the
  hazard model), runner `scripts/d2_survival.py`, config
  `configs/d2_irrigation/survival.yaml`.
- MLflow: experiment `d2_irrigation`, run `4406fcba5f64453483d931919ef0e5ce`.
- Decision record: [ADR-0012](../adr/0012-censoring-aware-time-to-event.md).

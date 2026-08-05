# ADR-0012: Censoring-aware time-to-event evaluation for the irrigation clock

- **Status:** Accepted
- **Date:** 2026-08-05
- **Deciders:** Sohan Shingade (+ mentor)

## Context
Every D2 layer so far scores a fixed-horizon question: the level at t+h, or
the probability of crossing a barrier within h hours. The operator question is
the transpose, hours until the block needs water, which is a time-to-event
problem. Two evaluation defects follow from forcing it into the fixed-horizon
frame. First, the stopping layer scores a decision window only when all h
future readings exist, which silently drops every decision cut short by a
sensor gap or the record end, and whether a window turns out complete is
unknown at decision time, so the rule conditions on the future. Second, a
single-horizon Brier score cannot compare models that answer "when" with a
full distribution over time. Survival analysis, standard in medical
statistics, has owned both problems for decades and is essentially absent
from the irrigation forecasting literature.

## Decision
Time-to-event questions in D2 are labeled and scored with survival machinery.
Labels are right-censored at the first missing reading or the record end
instead of dropped. Predictions are full survival curves S(h) on the hourly
grid 1 to 48. The score is the inverse-probability-of-censoring-weighted
Brier score (Graf et al. 1999) integrated over the grid (IBS), with the
censoring distribution estimated per fold by reverse Kaplan-Meier. The
reference ladder for skill is the training-fold Kaplan-Meier curve (the
survival null), the deterministic drydown calculator (current practice), and
the closed-form Brownian first passage (the literature's incumbent). Fold
cells where a reference IBS is degenerate (zero events, trivial prediction
perfect) are excluded from skill aggregates and the exclusion count is
printed; raw IBS rows are always kept. The ADR-0003 worst-fold gate is
unchanged and remains the promotion hurdle.

## Considered options
- **IPCW survival scoring with right-censored labels (chosen)**: uses every
  decision hour, removes the condition-on-the-future defect, and scores the
  whole timing distribution with one proper score.
- **Keep the fully-observed-window rule**: simple, but it deletes 98 to 139
  rows per probe on this record, exactly the rows near outages where a timing
  model earns its keep, and the deletion is future-dependent.
- **Score a point estimate of time-to-event (MAE on hours)**: undefined for
  censored rows without ad hoc imputation, and it throws away the uncertainty
  that makes the clock useful.

## Consequences
- **Good:** decisions near the June outage and the record end are scored for
  the first time; the evaluation now uses all 1409 decision hours per probe.
- **Good:** the discrete-time hazard regression becomes available as a model
  family, since its likelihood absorbs censoring natively, and it is the
  first model here that can represent diurnal timing.
- **Tradeoff:** IPCW assumes censoring is independent of the event given the
  covariates. Gap censoring is plausibly close to independent (shared gateway
  outages), yet end-of-record censoring is calendar-driven, so the weights
  are an approximation.
- **Cost:** reverse Kaplan-Meier and the weighted Brier are O(n·H) per fold;
  runtime impact is negligible.

Evidence: [survival clock report](../reports/2026-08-05-survival-clock.md);
code `vine.d2_irrigation.survival`.

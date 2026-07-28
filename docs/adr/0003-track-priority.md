# ADR-0003: Strict track priority + baseline-first methodology

- **Status:** Accepted
- **Date:** 2026-05-25
- **Deciders:** Sohan Shingade (+ mentor)

## Context
Three model tracks in 350 hours is real scope risk (named in the proposal). We
also need to avoid shipping complex models that don't actually beat simple ones.

## Decision
1. **Priority order:** D2 irrigation first (most data-rich, closest to pure
   time-series), D3 CV second (highest operational impact), D4 harvest third
   (sparse labels → scoped flexibly, may become exploratory).
2. **Baseline-first:** every track implements naive + rule-based baselines
   before any ML. No model ships unless it beats those baselines on held-out
   data, with quantitative evidence.

## Considered options
- **Sequential, baseline-gated (chosen)** — guarantees a working, evaluated
  deliverable at each phase; protects against scope blowout.
- **Parallel all three** — more breadth early but high risk none finishes well.
- **Skip baselines, go straight to deep learning** — faster to a demo, but no
  way to know if complexity is justified; brittle.

## Consequences
- **Good:** always something demonstrable; honest evaluation; clear cut line if
  time runs short (drop/curtail D4 first).
- **Bad:** CV (the flashiest track) starts later; baseline work feels
  unglamorous but is non-negotiable.

## Evidence log — the gate in action (D2)
The baseline-first gate has now rejected **eight** model families for D2
irrigation, all evaluated walk-forward against per-sensor persistence:
ridge, ridge+forecast, ridge-Δ, ARIMA, random forest, gradient-boosted trees,
a drydown rule — and (2026-07-09) a **globally-pooled cross-sensor model**
(`vine.d2_irrigation.pooled`, run via `scripts/d2_pooled.py`). The pooled rung
was the literature-motivated one: M4/M5 and Elsayed et al. (2021) attribute
ML's baseline-beating to cross-learning across related series, and IHV has five
near-identical probes sharing weather. Its first run was later superseded by the
causality correction below; the original numbers are retained in Git history,
not as current evidence.

A 2026-07-23 correction hardened this evidence and applied the same exact
`h−1` fold-boundary label purge to the pooled evaluator. The corrected
YAML-driven pooled GBT fleet skill is −45.1/−52.2/+33.0/+30.2% at
6/12/24/48 h. Its fleet worst-fold skill remains negative at every horizon
(−4.2% at 24 h and −35.5% at 48 h); only LS-4 has a non-negative worst fold
at 48 h. These pooled runs also use realized future-weather features, so their
positive long-horizon cells are oracle-assisted upper bounds; `ALL` is a
row-weighted micro-average of correlated sensor-hours, not independent fleet
replication. Pooled ridge loses fleet-wide at every horizon. Alert prevalence
is high enough that precision/recall alone cannot establish transition-detection
value. The same session completed a constrained **water-balance weather
correction**. After an adversarial review found and fixed the shared
fold-boundary label leak, its oracle-weather 48 h skill was positive across
five probes (+3.5…+11.2%) but every probe still had a negative worst fold
(−9.7…−34.1%) and LS-4 recall slipped 0.912→0.908. Water balance therefore
remains an **active experimental candidate** for archived-forecast/new-holdout
evaluation; it is not removed, but has not yet cleared the promotion gate.
Persistence remains the served fallback.

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

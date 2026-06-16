# ADR-0004: YAML + pydantic configs (defer Hydra)

- **Status:** Accepted
- **Date:** 2026-05-25
- **Deciders:** Sohan Shingade

## Context
Experiments must be reproducible from a config + seed, with no hyperparameters
hardcoded. Options range from plain YAML to full Hydra composition.

## Decision
Per-experiment **YAML files in `configs/`**, loaded via `vine.common.load_config`
and validated by a per-track **pydantic** model (`vine.<track>.config`).
Environment/process settings (paths, MLflow URI, seed) use `pydantic-settings`
from `.env`. Hydra is **deferred**, not rejected.

## Considered options
- **YAML + pydantic (chosen)** — minimal, readable (Karpathy aesthetic), typed
  validation with clear errors, zero magic; easy to diff and log to MLflow.
- **Hydra** — powerful config composition + multirun sweeps, but adds a
  framework, output-dir conventions, and a learning curve heavier than a solo
  project needs initially.
- **Plain argparse / dicts** — too easy to drift into hardcoded params; no
  validation.

## Consequences
- **Good:** simple, typed, reproducible; trivial to log the exact config.
- **Bad:** no built-in sweep/override composition — if we need large
  hyperparameter sweeps later, revisit Hydra in a superseding ADR. Hand-rolled
  config merging stays intentionally limited.

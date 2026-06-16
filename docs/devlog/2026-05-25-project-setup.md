# 2026-05-25 — Project setup & scaffolding

*Phase: Community Bonding (Weeks 1–3). Light schedule — UCSD finals run through
~June 7.*

## What I built
The skeleton everything else hangs off:

- **Repo structure** — single `vine` package, `src/` layout, one subpackage per
  deliverable (D1–D6), plus `configs/`, `docker/`, `k8s/`, and this wiki.
- **D1 pipeline core** — vegetation indices (NDVI/NDRE) as pure, tested
  functions, plus the interfaces for sensor reading, imagery tiling, block
  alignment, feature engineering, and data validation.
- **Tooling** — `uv` for envs/deps, `ruff` + `mypy` + `pytest` behind a single
  `make check` gate, pre-commit hooks, and GitLab CI mirroring that gate.
- **Reproducibility plumbing** — typed config loading, structured logging, and
  `seed_everything()`.
- **Claude Code setup** — `CLAUDE.md`, slash commands (`/new-experiment`,
  `/devlog`, `/adr`, `/model-card`), and subagents (geospatial, eval-reviewer,
  NRP deploy).

## Decisions
Recorded the foundational five as ADRs: monorepo `src/` layout (0001), `uv`
(0002), strict track priority + baseline-first (0003), YAML+pydantic configs
(0004), MLflow+DVC (0005).

## Results
No models yet — this phase is setup. `make check` passes on a clean checkout.

## Blockers / questions for mentor
- Exact sensor schema, units, sampling interval?
- Orthomosaic band order, resolution, CRS?
- How many seasons of historical harvest/irrigation data exist (drives D4 scope)?
- What labeled stress/pest imagery is available for supervised CV?
- NRP specifics: namespace, Ceph storage paths, MLflow hosting.

## Next two weeks
Stand up the real D1 ingestion against actual sensor + imagery samples, then
start D2 irrigation baselines (naive persistence + threshold rule) so there's a
bar for the forecasting models to clear.

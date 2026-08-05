# ADR-0001: Monorepo with `src/` layout, one package, subpackage per track

- **Status:** Accepted
- **Date:** 2026-05-25
- **Deciders:** Sohan Shingade

## Context
Three model tracks (irrigation, CV, harvest) share one data pipeline and one
evaluation framework (per the proposal). They could be separate repos, separate
installable packages in a workspace, or one package. We also need to decide
flat vs `src/` layout.

## Decision
A single repository, a single installable package `vine`, with one subpackage
per deliverable (`vine.d1_pipeline`, `vine.d2_irrigation`, `vine.d3_vision`, `vine.d4_harvest`,
`vine.d5_evaluation`, `vine.d6_serving`, `vine.common`), using the `src/` layout.

## Considered options
- **One package, `src/` layout (chosen)**: shared pipeline written once;
  imports resolve against the installed package so tests can't accidentally pick
  up the working dir; standard for distributable code.
- **uv workspace, multiple packages**: cleaner per-track dependency isolation,
  but more packaging overhead than a 350-hour solo project needs.
- **Flat layout**: simpler for tiny scripts, but error-prone imports and weaker
  packaging/CI story.
- **Separate repos per track**: defeats the "one shared pipeline" goal; high
  coordination cost.

## Consequences
- **Good:** DRY shared code; one CI config; one version; easy cross-track eval.
- **Bad:** all tracks' optional heavy deps live in one `pyproject.toml`
  (mitigated by per-track optional-dependency extras); a workspace split may
  be revisited if deploy images need tighter isolation.

# Contributing

This is a GSoC project, but the repo is public and built to outlive the summer.
Conventions below keep it reproducible and reviewable.

## Workflow

1. Branch from `main`: `track/<deliverable>-<short-desc>` (e.g.
   `irrigation/d2-lstm-encoder`).
2. **Explore → plan → implement.** For anything touching more than one file,
   write the plan first.
3. Work in small, shippable slices — each should end with something testable.
4. `make check` must pass locally before you push (CI runs the same gate).
5. Open an MR/PR with: what changed, results vs baseline (if a model),
   and links to any ADRs.

## Definition of done for a model

- Compared against the track's naive + rule-based baselines on **held-out**
  data (walk-forward for time series).
- Params + metrics logged to MLflow; run reproducible from config + seed.
- A [model card](../models/index.md) created or updated.
- The `eval-reviewer` subagent (or a human) has checked for leakage.

## Decisions

Architectural/tooling choices are recorded as [ADRs](../adr/index.md). Changing
one? Add a new ADR (or supersede an old one) — use the `/adr` command.

## Communication (GSoC)

- Weekly 1:1 with the mentor.
- Bi-weekly [devlog](../devlog/index.md) post (use the `/devlog` command).
- Active on the OSRE Slack channel.

## Code style

See [CLAUDE.md](https://gitlab.nrp-nautilus.io/) in the repo root — the short
version: minimal, readable, tutorial-like; pure functions for math; lazy imports
for heavy libs; type hints + Google-style docstrings; ruff line length 100.

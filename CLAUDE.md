# CLAUDE.md — VINE

AI/ML models for agricultural analytics at Iron Horse Vineyards, running on the
National Research Platform (NRP/Nautilus K8s). GSoC 2026. Three model tracks
(irrigation, plant-health CV, harvest timing) share one data pipeline.

This repo is **Track 2 (AI/ML Models)** of four VINE subprojects; it consumes
the data pipeline and feeds the digital twin (Omniverse) and web dashboard.
All compute + storage is on **NRP.ai** (free Kubernetes); data comes from the
**National Data Platform** (NDP, CKAN). See @docs/infrastructure.md.

**New session? Read @docs/STATE.md first** — it's the current-state / progress
tracker (what's done, verified endpoints, open questions, next actions).

Full context lives in the wiki — read before non-trivial work:
@docs/index.md · @docs/architecture.md · @docs/infrastructure.md

## Stack
- Python 3.11, **uv** for envs/deps (never pip/poetry/conda directly)
- pandas/numpy, scikit-learn; geo: rasterio/rioxarray/xarray/geopandas
- PyTorch (CV + LSTM), statsmodels/pmdarima/prophet (forecasting), XGBoost
- FastAPI inference, Docker, Kubernetes; MLflow + DVC for tracking/versioning
- NRP services: S3 `s3-west.nrp-nautilus.io` (datasets + MLflow artifacts),
  CephFS (checkpoints), GitLab registry, managed LLM `ellm.nrp-nautilus.io/v1`
- Data: live sensors via `vine.d1_pipeline.InfluxReader` (InfluxDB/ThingsBoard at IHV,
  bucket `ihv`); published exports via `vine.d1_pipeline.NDPClient` (CKAN). Pin with DVC.
  InfluxDB token is an NRP secret — env only, NEVER hardcode/commit it.
- `src/` layout, single package `vine`, one subpackage per deliverable

## Commands (use these, don't guess)
- `make setup` — create venv, install all extras, install pre-commit
- `make check` — lint + type + test. **The gate. Run before every commit/PR.**
- `make fmt` — auto-format and autofix (ruff)
- `make test` — pytest (skips `slow`/`gpu` marks)
- `uv run pytest tests/d1_pipeline/test_indices.py -q` — run a single test file
- `uv add <pkg> --optional <extra>` — add a dep to a track's extra, never edit
  pyproject deps by hand
- `make serve` / `make docs` — run the API / the wiki locally

## How we work (the rules that matter)
- **Explore → plan → implement.** For anything touching >1 file or unfamiliar
  code, plan first. If you can describe the diff in one sentence, just do it.
- **Evaluation-driven.** No model ships without beating naive + rule-based
  baselines on held-out data. Baselines live in `*/baselines.py`; metrics in
  `vine.d5_evaluation`. Quantitative evidence or it didn't happen.
- **Reproducible by construction.** Every run is determined by a YAML config +
  seed. Call `seed_everything()` at the start of training. Log params/metrics
  to MLflow. Never hardcode hyperparameters in code — put them in `configs/`.
- **Verify, then claim.** Run the check (`make check`, a test, the actual API
  call) and show output before saying something works.
- **Small, shippable slices.** Each 2-week phase ends with a working, testable
  component. No big-bang integration.

## Code style (where we differ from defaults)
- Match Karpathy's aesthetic: **minimal, readable, hackable.** Code should read
  like a tutorial. Prefer a clear function over a clever abstraction. Add a
  module docstring saying what it's for and which deliverable (D1–D6) it serves.
- Keep dependencies few; justify every new one in the PR.
- Pure, I/O-free functions for math (indices, metrics, features) — they're the
  unit-tested core. Push I/O to the edges.
- Heavy/optional libs (torch, rasterio, geopandas) are imported **lazily inside
  functions**, never at module top level, so the core installs light.
- Type hints on public functions. Google-style docstrings. ruff line length 100.

## Layout — folders follow the proposal timeline (see DELIVERABLES.md)
- `src/vine/d1_pipeline/` — D1 shared pipeline (sensors, imagery, indices, features, geo, validation)
- `src/vine/d2_irrigation/` D2 · `d3_vision/` D3 · `d4_harvest/` D4 · `d5_evaluation/` D5 · `d6_serving/` D6
- `src/vine/common/` — config, logging, seeding (import from here)
- `configs/`, `docker/`, `k8s/` mirror the same `d1_..d6_` grouping
- `configs/` — YAML experiment configs (the source of truth for runs)
- `docs/` — the wiki (architecture, data docs, model cards, ADRs, devlog)
- `data/` & `models/` — gitignored; tracked with DVC, never committed to git

## Gotchas
- `data/` and `models/` are DVC-tracked. **Never `git add` a `.tif`, `.pt`, or
  large CSV** — pre-commit blocks files >1 MB. Use `dvc add`.
- Sensor data is gappy/noisy. Never silently impute — flag gaps (see
  `vine.d1_pipeline.validation`). Distinguish sensor failure from real signal.
- GPU training runs **interactively on NRP pods**, not in GitLab CI. CI only
  lints + runs fast tests.
- Decisions are recorded as ADRs in `docs/adr/`. Changing a tool/approach
  choice? Add or supersede an ADR — don't just change code silently.

## Conventions
- Branches: `track/<deliverable>-<short-desc>` (e.g. `irrigation/d2-lstm-encoder`).
- Bi-weekly devlog post in `docs/devlog/` (GSoC requirement). Commit messages
  imperative, present tense.
- When unsure about data availability or scope, the answer is "confirm with
  mentor" — note it, don't invent data.
- **Keep state across sessions:** when status changes (input verified, deliverable
  advanced, decision made), update @docs/STATE.md and commit it. Decisions → an
  ADR in `docs/adr/`. Narrative progress → a `docs/devlog/` post.
- NRP specifics (namespace, storage classes, NDP API auth, S3/LLM tokens) are
  **confirmed with the mentor** — defaults in config are best-guess, not gospel.
  Tokens come from the NRP portal (`/s3token/`, `/llmtoken/`), never hardcoded.

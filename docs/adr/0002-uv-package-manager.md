# ADR-0002: `uv` for environment & dependency management

- **Status:** Accepted
- **Date:** 2026-05-25
- **Deciders:** Sohan Shingade

## Context
We need reproducible environments locally, in GitLab CI, and in Docker images on
NRP. Options: pip + venv + requirements.txt, Poetry, conda, or uv.

## Decision
Use [`uv`](https://docs.astral.sh/uv/) for everything: virtualenv creation,
dependency resolution, lockfile (`uv.lock`), and running commands (`uv run`).
`pyproject.toml` is the single dependency source; track deps are optional extras.

## Considered options
- **uv (chosen)**: very fast resolves/installs (matters in CI), one tool for
  venv + deps + lock + run, first-class `pyproject.toml`, official Docker images.
- **Poetry**: mature, good `pyproject.toml` support, but slower and historically
  fiddly with PyTorch/CUDA index URLs.
- **conda/mamba**: strong for binary geo/CUDA deps, but heavier, slower,
  reproducibility via env.yaml is looser, and wheels now cover rasterio/torch.
- **pip-tools**: minimal, but multiple files and no integrated run/venv story.

## Consequences
- **Good:** fast, reproducible (`uv.lock` committed), one mental model; CI uses
  the official `ghcr.io/astral-sh/uv` image.
- **Bad:** newer tool; some teammates may be unfamiliar (mitigated by `make`
  targets that wrap it). GPU/CUDA torch index pinning still needs care.

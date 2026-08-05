# ADR-0005: MLflow for tracking + DVC for data/model versioning

- **Status:** Accepted
- **Date:** 2026-05-25
- **Deciders:** Sohan Shingade (+ mentor)

## Context
The proposal requires reproducible experiment tracking (logged hyperparameters,
loss curves, metrics) and a way to version large data + model artifacts that
must not live in git. These are two distinct problems.

## Decision
- **MLflow** for experiment tracking: log params, metrics, and artifacts per
  run; self-hosted on NRP (no external account, unlike W&B).
- **DVC** for data + model versioning: `data/` and `models/` are DVC-tracked
  against Ceph/object storage; git holds only `.dvc` pointers.

## Considered options
- **MLflow + DVC (chosen)**: open-source, self-hostable, complementary
  (process-centric vs data-centric); no vendor lock-in; works inside NRP.
- **Weights & Biases**: excellent UX, but a hosted account and data leaving NRP;
  awkward for a public research project on academic infra.
- **Plain logging + git-LFS**: minimal, but no run comparison UI and git-LFS is
  a poor fit for multi-GB rasters.

## Consequences
- **Good:** reproducible, self-contained on NRP, open tooling the community can
  reuse; clean separation of "which run" (MLflow) from "which data" (DVC).
- **Bad:** two systems to operate; MLflow server + DVC remote both need setup on
  NRP (confirm storage with mentor). Discipline required to actually log every run.

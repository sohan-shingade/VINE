# ADR-0007: NRP.ai infrastructure mapping

- **Status:** Accepted
- **Date:** 2026-05-25
- **Deciders:** Sohan Shingade (+ mentor)

## Context
All compute and storage runs on the [National Research Platform](https://nrp.ai)
(NRP/Nautilus), a free, multi-tenant Kubernetes platform. We need to map each
VINE need to a concrete NRP service so deployment and storage choices aren't
ad hoc.

## Decision
Use these NRP services:

| Need | NRP service | Concrete target |
|------|-------------|-----------------|
| Interactive dev / training | JupyterHub + GPU pods | A100 / L40 / RTX A6000 |
| Container registry | GitLab registry | `gitlab-registry.nrp-nautilus.io` (group `ihv`) |
| Inference serving | Kubernetes Deployments/Jobs | namespaced; GPU only where needed |
| Dataset storage | **S3 (Ceph RGW)** | `https://s3-west.nrp-nautilus.io`, creds via portal `/s3token/` |
| Checkpoints / large intermediates | **CephFS** PVC | high parallel read/write |
| Small files / pip caches | RBD PVC | low latency |
| Experiment artifacts | MLflow → S3 backend | uses the S3 bucket above |
| Vector search (optional) | Milvus + `qwen3-embedding` | NRP managed |
| LLM (optional, e.g. NL block-health summaries) | Managed LLM | OpenAI-compatible `https://ellm.nrp-nautilus.io/v1`, token `/llmtoken/` |

## Considered options
- **NRP-native services (chosen)**: free, already provisioned for the org,
  keeps data on-platform, no external accounts.
- **External cloud (AWS/GCP)**: familiar, but costs money, moves data off NRP,
  and isn't what the project/mentor supports.

## Consequences
- **Good:** zero infra cost; data and compute co-located; reproducible images in
  the org registry; storage matched to access pattern (S3 datasets, CephFS
  checkpoints).
- **Bad:** tied to NRP conventions and fair-use limits (GPU reservations, LLM
  concurrency caps); exact namespace, storage classes, and quotas must be
  confirmed with the mentor. The managed LLM is optional and is not required by
  any of the three core model tracks.

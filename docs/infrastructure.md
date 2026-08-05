# Infrastructure: NRP.ai & the National Data Platform

VINE runs entirely on [NRP.ai](https://nrp.ai) (National Research Platform /
Nautilus), a free, NSF/DOE/DoD-funded, multi-tenant Kubernetes platform with
400+ nodes across 70+ sites, led by UC San Diego. Data comes from the
[National Data Platform](https://nationaldataplatform.org) (NDP). The project
uses no external cloud and has no hardware cost. Full mapping in
[ADR-0006](adr/0006-ndp-data-access.md) and [ADR-0007](adr/0007-nrp-infrastructure.md).

## VINE is four sibling subprojects

This repo is **Track 2: AI/ML Models**. It consumes the data pipeline and feeds
the visualization layers:

```
  ┌─ Track 1: Data Pipeline & Integration ─┐   (NDP ingestion, validation)
  │                                          ▼
  │            Track 2: AI/ML Models  ◀── THIS REPO
  │            (irrigation · CV · harvest)   │
  │                                          ├──▶ Track 3: Digital Twin (Omniverse)
  └──────────────────────────────────────────┴──▶ Track 4: Web Dashboard (React/FastAPI)
```

Related GitLab groups: `gitlab.nrp-nautilus.io/ihv` (Iron Horse Vineyards),
`gitlab.nrp-nautilus.io/omniverse` (digital twin).

## Data: live source vs publishing layer

- **Live source = InfluxDB** (verified). Sensors → ThingsBoard → InfluxDB bucket
  `ihv` at `https://nrp-thingsboard-influxdb.nrp-nautilus.io` (public HTTPS,
  token-gated). Pulled with `vine.d1_pipeline.InfluxReader`; see
  [ADR-0008](adr/0008-sensor-source-influxdb.md). Config: `VINE_INFLUX_*`.
- **National Data Platform (NDP)** = intended *publishing* layer for open,
  shareable exports. Its public site lists an Iron Horse org but does not
  expose a working CKAN API yet, so `vine.d1_pipeline.NDPClient` is a placeholder pending
  mentor confirmation ([ADR-0006](adr/0006-ndp-data-access.md)).
- Either way, raw pulls are snapshotted to `data/raw/` and pinned with DVC so a
  model's exact data version is recorded.

## Compute & storage on NRP

| Need | Service | Target |
|------|---------|--------|
| Training / interactive dev | JupyterHub + GPU pods | A100 / L40 / RTX A6000 |
| Inference serving | K8s Deployments / Jobs | see [`k8s/`](https://gitlab.nrp-nautilus.io/) |
| Container registry | GitLab registry | `gitlab-registry.nrp-nautilus.io` |
| **Datasets** | **S3 (Ceph)** | `https://s3-west.nrp-nautilus.io` · creds: portal `/s3token/` |
| **Checkpoints / large files** | **CephFS** PVC | high parallel throughput |
| Small files / pip | RBD PVC | low latency |
| Experiment artifacts | MLflow → S3 | same S3 bucket (boto3) |

Dashboards: [grafana.nrp-nautilus.io](https://grafana.nrp-nautilus.io) ·
[dash.nrp-nautilus.io](https://dash.nrp-nautilus.io).

## Managed LLM (optional)

NRP hosts an OpenAI-compatible LLM endpoint at
`https://ellm.nrp-nautilus.io/v1` (token from portal `/llmtoken/`), with models
like `qwen3` and `qwen3-embedding`, plus a Milvus vector DB. No core model track
requires it. It is available if we add natural-language block-health
summaries or semantic search over field notes for the dashboard. Config:
`VINE_NRP_LLM_BASE_URL`, `VINE_NRP_LLM_API_KEY`.

## Setup checklist (do once)

1. Get an NRP namespace + access (mentor sponsors).
2. Portal `/s3token/` → set `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`.
3. `uv tool install "dvc[s3]"` and point the DVC remote at the S3 bucket.
4. (Optional) Portal `/llmtoken/` → set `VINE_NRP_LLM_API_KEY`.
5. Confirm exact namespace, storage classes, and NDP API auth with the mentor.

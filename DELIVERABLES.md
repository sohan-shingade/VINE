# Deliverables map

The repo is organized to follow the proposal's timeline. Every layer (code,
configs, containers, deployment) is grouped by deliverable D1 → D6 and the
folder list reads top to bottom like the proposal. Progress: see
[`docs/STATE.md`](docs/STATE.md).

| # | Deliverable | Code (`src/vine/`) | Configs | Container | Deploy (`k8s/`) | Status |
|---|-------------|--------------------|---------|-----------|-----------------|--------|
| **D1** | Data ingestion & feature pipeline | `d1_pipeline/` | `configs/d1_pipeline/` | `docker/d1_ingest.Dockerfile` | `k8s/d1_ingest/` | ☑ |
| **D2** | Irrigation scheduling (forecasting) | `d2_irrigation/` | `configs/d2_irrigation/` | `docker/d2_irrigation.Dockerfile` | `k8s/d6_serving/` | ☑ persistence champion |
| **D3** | Plant-health computer vision | `d3_vision/` | `configs/d3_vision/` | `docker/d3_vision.Dockerfile` | `k8s/d6_serving/` | ☑ label-free screening |
| **D4** | Harvest-timing forecasting | `d4_harvest/` | `configs/d4_harvest/` | `docker/d4_harvest.Dockerfile` | `k8s/d6_serving/` | ☑ exploratory (labels absent) |
| **D5** | Cross-track evaluation | `d5_evaluation/` | — | — | — | ☑ |
| **D6** | NRP deployment (FastAPI services) | `d6_serving/` | — | (per-track images above) | `k8s/d6_serving/` | ◐ local API |
| **D7** | Documentation & devlog | — | — | — | — | ☑ ([wiki](docs/index.md)) |

Cross-cutting (not a deliverable): `src/vine/common/` (config, logging, seeding).

**Timeline** (proposal): D1 weeks 3 to 5 → D2 weeks 5 to 7 → D3 weeks 7 to 9 →
D4+D5 weeks 9 to 10 → D6 weeks 11 to 12 → D7 weeks 12 to 13. Full schedule:
[`docs/roadmap.md`](docs/roadmap.md).

## Extras map (install only what a deliverable needs)

```bash
uv sync --extra sensors            # D1 sensor ingestion (InfluxDB)
uv sync --extra geo                # D1 imagery / raster stack
uv sync --extra irrigation         # D2
uv sync --extra vision             # D3
uv sync --extra harvest            # D4
uv sync --extra track              # D5 tracking (MLflow)
uv sync --extra serve              # D6 FastAPI
uv sync --all-extras               # everything (default for dev)
```

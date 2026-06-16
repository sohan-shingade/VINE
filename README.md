# 🍇 VINE — Vineyard Intelligence Network & Environment

[![CI](https://gitlab.nrp-nautilus.io/)](https://gitlab.nrp-nautilus.io/) · License: MIT · GSoC 2026

**AI/ML models for agricultural analytics on [NRP.ai](https://nrp.ai).**
VINE turns LoRaWAN sensor streams and multispectral drone imagery from Iron
Horse Vineyards (data hosted on the [National Data Platform](https://nationaldataplatform.org))
into actionable predictions: **when to irrigate, which blocks are stressed, and
when to harvest.** This repo is **Track 2 (AI/ML Models)** of the VINE project.

| Track | Deliverable | Predicts |
|-------|-------------|----------|
| 💧 Irrigation | D2 | Soil moisture (6/12/24/48 h) → irrigation recommendation |
| 🌿 Plant health (CV) | D3 | Per-block stress / pest from multispectral imagery |
| 🍇 Harvest timing | D4 | Per-block harvest-readiness score |

All three share one data pipeline (**D1**), one evaluation framework (**D5**),
and deploy as FastAPI services on NRP Kubernetes (**D6**).

## Quickstart

```bash
make setup      # uv venv + all extras + pre-commit
make check      # lint + type + fast tests (the gate)
make serve      # run the inference API locally
make docs       # browse the wiki at http://127.0.0.1:8000
```

Requires Python 3.11 and [`uv`](https://docs.astral.sh/uv/).

## Repository layout

```
src/vine/
  data/         D1  shared pipeline: sensors, imagery, indices, features, geo, validation
  irrigation/   D2  ARIMA/Prophet/LSTM soil-moisture forecasting
  cv/           D3  ResNet/EfficientNet plant-health classification
  harvest/      D4  XGBoost/LSTM harvest timing
  eval/         D5  shared metrics + baseline comparison
  serving/      D6  FastAPI inference app
  common/           config, logging, reproducible seeding
configs/        YAML experiment configs (source of truth for runs)
docker/ k8s/    D6  container images + Nautilus manifests
docs/           D7  the wiki (architecture, data, model cards, ADRs, devlog)
tests/          pytest suite
```

## Documentation

The wiki lives in [`docs/`](docs/index.md) (build with `make docs`):
[Architecture](docs/architecture.md) ·
[Infrastructure (NRP & NDP)](docs/infrastructure.md) ·
[Getting started](docs/guides/getting-started.md) ·
[Data datasheet](docs/data/index.md) ·
[Decisions (ADRs)](docs/adr/index.md) ·
[Devlog](docs/devlog/index.md) · [Roadmap](docs/roadmap.md)

## Methodology in one line

Climb the complexity ladder — naive → classical → deep learning — and **nothing
ships unless it beats its baseline on held-out data.** Every run is reproducible
from a config + seed, logged to MLflow, with data versioned by DVC.

## People

Contributor: **Sohan Shingade** (UC San Diego) · Mentor: **Mohammad Firas Sada**
(UCSD) · Org: OSRE / National Research Platform.

## License

[MIT](LICENSE).

# Architecture

VINE is a single Python package (`vine`) with one subpackage per deliverable.
All three model tracks consume the same data pipeline, so feature engineering
and evaluation are written once.

> This repo is **Track 2 (AI/ML Models)** of four VINE subprojects. It pulls
> data from the [National Data Platform](infrastructure.md) and serves
> predictions to the digital twin and web dashboard. Compute + storage run on
> [NRP.ai](infrastructure.md). See [Infrastructure](infrastructure.md).

## System view

```
   Sensors (LoRaWAN)        Drone imagery (GeoTIFF)      Historical records
   soil moisture, temp,     RGB + NIR + Red-edge         harvest dates, yields,
   CO2, humidity            multispectral orthomosaics   irrigation logs
        │                          │                          │
        └──────────────┬───────────┴──────────────┬───────────┘
                       ▼                           ▼
              ┌─────────────────────────────────────────┐
              │  D1  vine.d1_pipeline  — shared pipeline         │
              │  sensors · imagery · indices (NDVI/NDRE)  │
              │  geo (block alignment) · features · valid │
              └─────────────────────────────────────────┘
                       │              │              │
            ┌──────────┘     ┌────────┘     └────────┐
            ▼                ▼                        ▼
   ┌────────────────┐ ┌────────────────┐   ┌────────────────┐
   │ D2 irrigation  │ │ D3 cv          │   │ D4 harvest     │
   │ ARIMA/Prophet/ │ │ ResNet/EffNet  │   │ XGBoost/LSTM   │
   │ LSTM forecast  │ │ stress/pest    │   │ readiness      │
   └────────────────┘ └────────────────┘   └────────────────┘
            └────────────────┬─────────────────────┘
                             ▼
                   ┌──────────────────────┐
                   │ D5 vine.d5_evaluation          │  baselines, metrics,
                   │ walk-forward, vs base │  ablations, reports
                   └──────────────────────┘
                             ▼
                   ┌──────────────────────┐
                   │ D6 vine.d6_serving       │  FastAPI → Docker → NRP K8s
                   │ /irrigation /health   │  → VINE dashboard & digital twin
                   │ /harvest  /healthz    │
                   └──────────────────────┘
```

## Package map

| Path | Deliverable | Responsibility |
|------|-------------|----------------|
| `src/vine/d1_pipeline/` | D1 | Ingest sensors + imagery, vegetation indices, features, validation, block alignment |
| `src/vine/d2_irrigation/` | D2 | Soil-moisture forecasting + irrigation decision layer |
| `src/vine/d3_vision/` | D3 | Multispectral plant-health classification, pest detection, yield |
| `src/vine/d4_harvest/` | D4 | Per-block harvest-readiness + days-to-harvest |
| `src/vine/d5_evaluation/` | D5 | Shared metrics, walk-forward validation, baseline comparison |
| `src/vine/d6_serving/` | D6 | FastAPI inference app |
| `src/vine/common/` | — | Config, structured logging, reproducible seeding |
| `configs/` | — | YAML experiment configs (source of truth for every run) |
| `docker/`, `k8s/` | D6 | Container images + Nautilus manifests |
| `docs/` | D7 | This wiki |

## Design principles

1. **One pipeline, three tracks.** Shared feature engineering lives in
   `vine.d1_pipeline`; tracks never re-implement ingestion.
2. **Climb the complexity ladder.** Every track starts with a naive baseline,
   then classical, then deep learning — each compared against the rung below.
   Nothing ships without beating its baseline ([ADR-0003](adr/0003-track-priority.md)).
3. **Reproducible by construction.** A run = config + seed. Params and metrics
   go to MLflow; data and models are versioned with DVC
   ([ADR-0005](adr/0005-experiment-tracking.md)).
4. **Pure core, I/O at the edges.** Math (indices, metrics, features) is pure
   and unit-tested; heavy libs (torch, rasterio) are imported lazily.
5. **Minimal and readable** (Karpathy aesthetic) — code reads like a tutorial;
   few dependencies, each justified.

## Data flow contracts

- **Sensors** → tidy frame indexed by UTC timestamp, resampled to a regular grid
  with explicit gap flags (never silent imputation).
- **Imagery** → 7-channel patches `[R, G, B, NIR, RedEdge, NDVI, NDRE]` aligned
  to vineyard-block polygons.
- **Predictions** → always reported **per vineyard block**, with confidence
  where the model supports it, exposed over the REST API.

## Priority & scope

Strict ordering when time is tight ([ADR-0003](adr/0003-track-priority.md)):
**D2 irrigation** first (most data-rich), **D3 CV** second (highest impact),
**D4 harvest** third (sparse labels → may become exploratory).

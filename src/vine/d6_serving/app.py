"""FastAPI inference service. One app, three routers (one per model track).

Endpoints mirror the proposal's API design and feed the VINE dashboard and
digital twin:

    GET  /irrigation/forecast?block_id=X  -> soil moisture + irrigation rec
    POST /health/analyze                  -> stress class + NDVI score
    GET  /harvest/readiness?block_id=X    -> readiness score + confidence

Run locally with `make serve`. Containerized per track in docker/.
Requires the `serve` extra.
"""

from __future__ import annotations

from fastapi import FastAPI

from vine import __version__

app = FastAPI(title="VINE Inference API", version=__version__)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """Kubernetes liveness/readiness probe."""
    return {"status": "ok", "version": __version__}


@app.get("/irrigation/forecast")
def irrigation_forecast(block_id: str) -> dict[str, object]:
    """Predicted soil moisture + irrigation recommendation for a block."""
    # TODO(D6): load model, return horizon forecasts + recommendation.
    return {"block_id": block_id, "forecast": None, "recommend_irrigation": None}


@app.get("/harvest/readiness")
def harvest_readiness(block_id: str) -> dict[str, object]:
    """Harvest-readiness score (0-1) + confidence interval for a block."""
    # TODO(D6): load model, return readiness + CI + days-to-harvest.
    return {"block_id": block_id, "readiness": None, "ci": None}

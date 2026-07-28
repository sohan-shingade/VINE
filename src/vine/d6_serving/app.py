"""FastAPI inference service for D6 model predictions.

The irrigation endpoint serves the shipped D2 persistence model from sensor
snapshots. Run locally with ``make serve`` or build its per-track image from
``docker/d2_irrigation.Dockerfile``.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException

from vine import __version__
from vine.common import get_logger
from vine.common.config import REPO_ROOT, load_config
from vine.d1_pipeline.ingest import load_snapshot
from vine.d6_serving.irrigation import (
    IrrigationForecast,
    IrrigationServingConfig,
    NoReadingError,
    UnknownBlockError,
    build_irrigation_forecast,
)

log = get_logger(__name__)
app = FastAPI(title="VINE Inference API", version=__version__)

_SERVING_CONFIG_PATH = Path(
    os.environ.get(
        "VINE_SERVING_CONFIG",
        str(REPO_ROOT / "configs/d6_serving/irrigation.yaml"),
    )
)
_SERVING_CONFIG = IrrigationServingConfig(**load_config(_SERVING_CONFIG_PATH))


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """Return process health for Kubernetes probes."""
    return {"status": "ok", "version": __version__}


@app.get("/irrigation/forecast", response_model=IrrigationForecast)
def irrigation_forecast(block_id: str) -> IrrigationForecast:
    """Return a persistence forecast and threshold advice for a vineyard block."""
    try:
        return build_irrigation_forecast(block_id, _SERVING_CONFIG, load_snapshot)
    except UnknownBlockError as exc:
        raise HTTPException(status_code=404, detail=f"unknown block: {block_id}") from exc
    except (NoReadingError, FileNotFoundError) as exc:
        log.warning(
            "irrigation forecast unavailable",
            block_id=block_id,
            error_type=type(exc).__name__,
            error=str(exc),
        )
        raise HTTPException(
            status_code=503,
            detail="irrigation forecast temporarily unavailable",
        ) from exc


@app.get("/harvest/readiness")
def harvest_readiness(block_id: str) -> dict[str, object]:
    """Return the placeholder harvest-readiness contract for a block."""
    # TODO(D6): load model, return readiness + CI + days-to-harvest.
    return {"block_id": block_id, "readiness": None, "ci": None}

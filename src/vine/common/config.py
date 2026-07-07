"""Configuration: environment settings + typed YAML experiment configs.

Two layers, kept deliberately simple (see docs/adr/0004-config-management.md):

1. `Settings` — process/environment config (paths, MLflow URI, seed) from
   environment variables / `.env`. One instance, `settings`.
2. `load_config(path)` — per-experiment YAML loaded into a plain dict, with
   the chosen track's pydantic model used to validate it. Run-specific.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Environment/process configuration. Read once at import time."""

    model_config = SettingsConfigDict(env_prefix="VINE_", env_file=".env", extra="ignore")

    data_dir: Path = REPO_ROOT / "data"
    models_dir: Path = REPO_ROOT / "models"
    seed: int = 42
    log_level: str = "INFO"
    k8s_namespace: str = "ihv"  # our NRP namespace

    # Experiment tracking (MLflow self-hosted on NRP; empty -> local ./mlruns).
    mlflow_tracking_uri: str = ""

    # InfluxDB — primary live sensor source (ThingsBoard/LoRaWAN at IHV).
    # Token comes from the NRP secret; never hardcode it.
    influx_url: str = "https://nrp-thingsboard-influxdb.nrp-nautilus.io"
    influx_org: str = "Iron Horse Vineyards"
    influx_bucket: str = "ihv"
    influx_token: str = ""

    # National Data Platform (NDP) — discovery catalog (CKAN API under /catalog).
    # Points to where data lives (InfluxDB, NextCloud/STAC); does not host bytes.
    ndp_base_url: str = "https://nationaldataplatform.org/catalog"
    ndp_org: str = "iron-horse-vineyards"
    ndp_api_key: str = ""  # set VINE_NDP_API_KEY for private datasets

    # Drone imagery — NextCloud public share (files) + STAC catalog (index).
    # The share token is the public link id, not a secret. STAC asset hrefs
    # are stale — walk the share's WebDAV tree instead (vine.d1_pipeline.webdav).
    imagery_share_url: str = "https://nextcloud.nrp-nautilus.io/s/ieAqEKDDKeYq9q4"
    stac_collection_url: str = (
        "https://ndp-test.sdsc.edu/stac/collections/IHV_DJI_MULTISPECTRAL_DCIM"
    )

    # Weather — historical archive via Open-Meteo (ERA5), free, no key.
    # Gridded to the vineyard coordinates (see ADR-0009). Forecast TBD.
    weather_archive_url: str = "https://archive-api.open-meteo.com/v1/archive"
    vineyard_lat: float = 38.457  # Iron Horse Vineyards, Sebastopol CA
    vineyard_lon: float = -122.896

    # NRP object storage (S3-compatible Ceph). Creds from the NRP portal
    # /s3token/ via standard AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY.
    s3_endpoint_url: str = "https://s3-west.nrp-nautilus.io"

    # NRP managed LLM (OpenAI-compatible). Token from the NRP portal /llmtoken/.
    nrp_llm_base_url: str = "https://ellm.nrp-nautilus.io/v1"
    nrp_llm_api_key: str = ""


settings = Settings()


def load_config(path: str | Path) -> dict[str, Any]:
    """Load a YAML experiment config into a dict.

    Validate it against a track-specific pydantic model before training, e.g.::

        cfg = load_config("configs/irrigation/lstm.yaml")
        params = IrrigationConfig(**cfg)
    """
    with open(path) as f:
        return yaml.safe_load(f)

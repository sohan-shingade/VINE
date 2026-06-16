# Getting started

## Prerequisites

- Python 3.11 (`.python-version` pins it)
- [`uv`](https://docs.astral.sh/uv/) — install: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- For the geospatial pipeline, GDAL is pulled in via `rasterio` wheels (no system GDAL needed on most platforms).

## Setup

```bash
git clone <repo-url> vine && cd vine
make setup        # creates .venv, installs all extras, installs pre-commit hooks
make check        # lint + type + test — should pass on a clean checkout
```

`make setup` runs `uv sync --all-extras`. To install only one track's deps:

```bash
uv sync --extra irrigation        # D2 only
uv sync --extra cv --extra serve  # D3 + serving
```

## Everyday commands

| Command | What it does |
|---------|--------------|
| `make check` | The gate: lint + type + fast tests. Run before every commit. |
| `make fmt` | Auto-format + autofix with ruff |
| `make test` | Run tests (skips `slow`/`gpu` marks) |
| `make serve` | Run the FastAPI inference API locally |
| `make docs` | Serve this wiki at http://127.0.0.1:8000 |
| `uv run vine version` | Run the CLI |

## Running an experiment

Every run is driven by a YAML config so it's reproducible from config + seed:

```bash
uv run vine train irrigation configs/d2_irrigation/lstm.yaml
```

Use the `/new-experiment` Claude command to scaffold a new config from an
existing one.

## Data

`data/` and `models/` are **gitignored** and versioned with DVC, not git.
On NRP they map to Ceph-backed persistent volumes. See the
[datasheet](../data/index.md) for what the data is and how it's organized.

DVC is a standalone CLI (not a project dependency — see
[ADR-0005](../adr/0005-experiment-tracking.md)). Install it once:

```bash
uv tool install "dvc[s3]"   # or pipx install "dvc[s3]"
```

## NRP / GPU

Model training runs interactively on NRP GPU pods (A100 / L40 / RTX A6000) via
JupyterHub or `kubectl`. GitLab CI only lints and runs fast tests — it never
trains. Deployment manifests live in `k8s/`. Full service mapping:
[Infrastructure](../infrastructure.md).

One-time NRP setup:

```bash
# 1. S3 credentials (NRP portal → /s3token/) for datasets + MLflow artifacts
export AWS_ACCESS_KEY_ID=...      # or put in .env
export AWS_SECRET_ACCESS_KEY=...
# 2. DVC remote pointed at NRP S3
dvc remote add -d nrp s3://vine-data
dvc remote modify nrp endpointurl https://s3-west.nrp-nautilus.io
# 3. (optional) managed LLM token (NRP portal → /llmtoken/)
export VINE_NRP_LLM_API_KEY=...
```

## Fetching data from the National Data Platform

```python
from vine.d1_pipeline import NDPClient

ndp = NDPClient()                       # base URL + org from config/.env
datasets = ndp.list_org_datasets()      # Iron Horse Vineyards datasets
ndp.download_resource(url, "data/raw/sensors.csv")
```

Then `dvc add data/raw/...` to pin the snapshot. Confirm the exact NDP API path
and whether an API key is needed with the mentor.

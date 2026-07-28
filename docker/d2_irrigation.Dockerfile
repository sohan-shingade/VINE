# D6 — irrigation persistence inference image.
# Build locally:
#   docker build -f docker/d2_irrigation.Dockerfile -t vine-d2-irrigation:local .
ARG UV_IMAGE=ghcr.io/astral-sh/uv:python3.11-bookworm-slim@sha256:4f5d923c9dcea037f57bda425dd209f3ec643da2f0b74227f68d09dab0b3bb36
ARG PYTHON_IMAGE=python:3.11-slim-bookworm@sha256:b18992999dbe963a45a8a4da40ac2b1975be1a776d939d098c647482bcad5cba

FROM ${UV_IMAGE} AS build
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/
# Persistence serving reads Parquet snapshots; it needs sensors + serve, not the
# training-only irrigation stack (torch, Prophet, pmdarima).
RUN uv sync --frozen --no-dev --no-editable --extra sensors --extra serve

FROM ${PYTHON_IMAGE} AS runtime
WORKDIR /app
RUN groupadd --system --gid 10001 vine \
    && useradd --system --uid 10001 --gid vine --home-dir /app --no-create-home vine
COPY --from=build --chown=vine:vine /app/.venv /app/.venv
COPY --chown=vine:vine configs/d6_serving/irrigation.yaml /app/configs/d6_serving/irrigation.yaml
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VINE_DATA_DIR=/app/data \
    VINE_SERVING_CONFIG=/app/configs/d6_serving/irrigation.yaml
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).read()"]
CMD ["uvicorn", "vine.d6_serving.app:app", "--host", "0.0.0.0", "--port", "8000"]

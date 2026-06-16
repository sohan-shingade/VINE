# D6 — plant-health CV inference image (GPU-capable base on NRP).
# Build:  docker build -f docker/d3_vision.Dockerfile -t vine-d3-vision .
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS build
WORKDIR /app
COPY pyproject.toml uv.lock* README.md ./
COPY src/ ./src/
RUN uv sync --frozen --no-dev --extra vision --extra geo --extra serve

FROM python:3.11-slim-bookworm
WORKDIR /app
RUN useradd -m vine && apt-get update \
    && apt-get install -y --no-install-recommends curl libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /app /app
ENV PATH="/app/.venv/bin:$PATH"
USER vine
EXPOSE 8000
HEALTHCHECK CMD curl -f http://localhost:8000/healthz || exit 1
CMD ["uvicorn", "vine.d6_serving.app:app", "--host", "0.0.0.0", "--port", "8000"]

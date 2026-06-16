# D6 — harvest-timing inference image.
# Build:  docker build -f docker/d4_harvest.Dockerfile -t vine-d4-harvest .
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS build
WORKDIR /app
COPY pyproject.toml uv.lock* README.md ./
COPY src/ ./src/
RUN uv sync --frozen --no-dev --extra harvest --extra serve

FROM python:3.11-slim-bookworm
WORKDIR /app
RUN useradd -m vine
COPY --from=build /app /app
ENV PATH="/app/.venv/bin:$PATH"
USER vine
EXPOSE 8000
HEALTHCHECK CMD curl -f http://localhost:8000/healthz || exit 1
CMD ["uvicorn", "vine.d6_serving.app:app", "--host", "0.0.0.0", "--port", "8000"]

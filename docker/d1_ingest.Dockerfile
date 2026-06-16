# D1 — sensor ingestion image (runs `vine ingest` as an NRP CronJob).
# Build:  docker build -f docker/d1_ingest.Dockerfile -t vine-d1-ingest .
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS build
WORKDIR /app
COPY pyproject.toml uv.lock* README.md ./
COPY src/ ./src/
RUN uv sync --frozen --no-dev --extra sensors --extra track

FROM python:3.11-slim-bookworm
WORKDIR /app
RUN useradd -m vine
COPY --from=build /app /app
ENV PATH="/app/.venv/bin:$PATH"
USER vine
ENTRYPOINT ["vine"]
CMD ["ingest", "--start=-7d"]

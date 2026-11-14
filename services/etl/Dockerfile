# ETL image: used by `docker compose run etl` locally and optionally by CI.
# Build from the repo root: docker build -f services/etl/Dockerfile .
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 UV_PYTHON_DOWNLOADS=never UV_NO_CACHE=1 \
    FASTF1_CACHE=/cache/fastf1 OPENF1_CACHE_DIR=/cache/openf1
WORKDIR /app

# Dependencies first for layer caching.
COPY pyproject.toml uv.lock ./
COPY packages/racemodel/pyproject.toml packages/racemodel/
COPY services/api/pyproject.toml services/api/
COPY services/etl/pyproject.toml services/etl/
RUN uv sync --frozen --no-dev --package pitwall-etl --no-install-workspace

COPY packages/racemodel packages/racemodel
COPY services/etl services/etl
RUN uv sync --frozen --no-dev --package pitwall-etl

RUN useradd --create-home etl && mkdir -p /cache && chown etl /cache
USER etl
VOLUME /cache
ENV PATH="/app/.venv/bin:$PATH"
ENTRYPOINT ["pitwall-etl"]

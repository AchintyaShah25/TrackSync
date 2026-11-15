# API image for Render (free plan): small, no FastF1, non-root.
# Build from the repo root: docker build -f services/api/Dockerfile .
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 UV_PYTHON_DOWNLOADS=never UV_NO_CACHE=1 \
    PATH="/app/.venv/bin:$PATH" PORT=8000
WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY packages/racemodel/pyproject.toml packages/racemodel/
COPY services/api/pyproject.toml services/api/
COPY services/etl/pyproject.toml services/etl/
RUN uv sync --frozen --no-dev --package tracksync-api --no-install-workspace

COPY packages/racemodel packages/racemodel
COPY services/api services/api
RUN uv sync --frozen --no-dev --package tracksync-api

RUN useradd --create-home api
USER api
WORKDIR /app/services/api
EXPOSE 8000
# Render sets $PORT; one worker keeps memory low on the free instance.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 1 --proxy-headers"]

# RegulAI — single shared image for FastAPI + Dagster + scripts.
#
# Build:        docker build -t regulai-app:dev .
# Run FastAPI:  docker run -p 8765:8765 regulai-app:dev uv run uvicorn api.main:app --host 0.0.0.0 --port 8765
# Run Dagster:  docker run -p 3000:3000 regulai-app:dev uv run dagster dev -m dagster_project --host 0.0.0.0 --port 3000
#
# In production we use docker-compose.yml which sets each service's command.
#
# Two-stage build:
#   - stage 1 (`builder`) — install python+deps in a uv-managed venv
#   - stage 2 (`runtime`) — slim runtime, copy the venv + source

ARG PYTHON_VERSION=3.12-slim-bookworm

# ────────────────────────────────────────────────────────────────────
# Stage 0: build the React workstation (web/) → web/dist
# Built with VITE_API_MODE=live so it calls the real API (no MSW mocks),
# and Vite base=/app/ (production mode) so assets resolve under the
# FastAPI /app mount.
# ────────────────────────────────────────────────────────────────────
FROM node:20-bookworm-slim AS web-builder
RUN npm install -g pnpm@9
WORKDIR /web
COPY web/ ./
RUN pnpm install --no-frozen-lockfile \
    && VITE_API_MODE=live VITE_ENGINE_LABEL=Databricks pnpm build

# ────────────────────────────────────────────────────────────────────
# Stage 1: build deps with uv
# ────────────────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION} AS builder

# uv from official image — fast, deterministic Python dep installer.
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /uvx /usr/local/bin/

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_PREFERENCE=only-system \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Build deps that pyarrow / snowflake-connector-python sometimes need.
# Pinned to apt-get to keep the layer cacheable.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        git \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Resolve + install deps without the source code — keeps this layer
# cached when only Python files change but not the lock file.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --extra dev --extra databricks

# Now copy source + install the project itself (editable).
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --extra dev --extra databricks

# Seed the DB Crawler's demo source databases into the image. DuckDB + SQLite
# only (core dep + stdlib) — deterministic, no external services — so
# /admin/crawler works out of the box in production. Regenerated on every build,
# so it never depends on local host state.
RUN uv run python -m scripts.seed_source_dbs

# ────────────────────────────────────────────────────────────────────
# Stage 2: runtime
# ────────────────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION} AS runtime

# Minimal runtime deps. `make` is needed because some of our scripts
# are invoked via make targets (e.g. rebuild-kg chain in deploy docs).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        make \
        ca-certificates \
        curl \
        tini \
    && rm -rf /var/lib/apt/lists/*

# uv in runtime too — `uv run` is how our Makefile invokes Python.
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /uvx /usr/local/bin/

# Non-root user. UID 1000 plays well with bind-mounted host volumes
# during local docker-compose dev. Override with build-arg if needed.
ARG APP_UID=1000
RUN useradd --uid ${APP_UID} --user-group --create-home --shell /bin/bash regulai

WORKDIR /app
COPY --from=builder --chown=regulai:regulai /app /app
# The built React workstation, served by FastAPI at /app (see api/main.py).
COPY --from=web-builder --chown=regulai:regulai /web/dist /app/web/dist

# Make uv use the venv from the builder image without re-resolving.
ENV PATH="/app/.venv/bin:${PATH}" \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_PYTHON_PREFERENCE=only-system \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # Bind mounts override these for dev; production volumes provide them.
    DAGSTER_HOME=/app/.dagster_home \
    REGULAI_UPLOADS_ROOT=/app/materialized/uploads

# Pre-create writable dirs the app expects.
RUN mkdir -p ${DAGSTER_HOME} ${REGULAI_UPLOADS_ROOT} \
    && chown -R regulai:regulai ${DAGSTER_HOME} ${REGULAI_UPLOADS_ROOT}

USER regulai

# Tini ensures signals (SIGTERM) reach the python process — without it,
# `docker stop` waits for the default 10s grace period then SIGKILLs.
ENTRYPOINT ["/usr/bin/tini", "--"]

# Default command runs the FastAPI app; compose overrides this per service.
EXPOSE 8765 3000
CMD ["uv", "run", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8765"]

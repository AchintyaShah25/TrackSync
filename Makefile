# TrackSync developer commands. Every tool runs from inside this repo (docs/decisions/0003).

SHELL := /bin/bash
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))

# Project-local Python toolchain: uv-managed CPython lives in .tools, never on PATH.
export UV_PYTHON_INSTALL_DIR := $(ROOT)/.tools/python
export UV_CACHE_DIR := $(ROOT)/.tools/uv-cache
export UV_PYTHON_PREFERENCE := only-managed
# FastF1 reads FASTF1_CACHE natively; without it, it writes to ~/Library/Caches/fastf1.
export FASTF1_CACHE ?= $(ROOT)/.cache/fastf1
export OPENF1_CACHE_DIR ?= $(ROOT)/.cache/openf1
# Supabase CLI: keep its home dir in the repo and turn telemetry off.
export SUPABASE_HOME := $(ROOT)/.tools/supabase-home
export SUPABASE_TELEMETRY_DISABLED := 1
export DO_NOT_TRACK := 1
# Next.js telemetry (it ignores DO_NOT_TRACK).
export NEXT_TELEMETRY_DISABLED := 1

# Local settings and secrets (LLM keys) from .env when present. .env is never committed.
-include .env
export GROQ_API_KEY GEMINI_API_KEY

UV := uv
SUPABASE := pnpm exec supabase
LOCAL_DB_URL := postgresql://postgres:postgres@127.0.0.1:54322/postgres
DATABASE_URL ?= $(LOCAL_DB_URL)
export DATABASE_URL

.PHONY: e2e help bootstrap clean-tools up down db-up migrate db-reset db-size etl test test-py test-web lint lint-py lint-web fmt eval rag-backfill

help: ## List commands
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  %-12s %s\n", $$1, $$2}'

bootstrap: ## Install Python 3.12, the venv, node deps, and the Supabase CLI (all repo-local)
	$(UV) python install 3.12 --no-bin
	$(UV) sync --all-packages
	pnpm install
	@mkdir -p $(FASTF1_CACHE) $(OPENF1_CACHE_DIR)
	@test -f .env || cp .env.example .env

clean-tools: ## Remove every repo-local toolchain and cache
	rm -rf .tools .venv node_modules apps/web/node_modules .cache

db-up: ## Start only the local Postgres
	$(SUPABASE) db start

# Postgres + Auth (gotrue), its gateway (kong) and Mailpit (read magic-link emails at
# http://127.0.0.1:54324). Everything else stays off (decision 0031).
SUPABASE_UNUSED := realtime,storage-api,imgproxy,postgrest,postgres-meta,studio,edge-runtime,logflare,vector,supavisor
stack-up: ## Start local Postgres + Supabase Auth (for sign-in)
	$(SUPABASE) start -x $(SUPABASE_UNUSED)

up: stack-up migrate ## Local Postgres + Auth + api + web (decision 0031)
	docker compose up --build

down: ## Stop app containers and the local Supabase stack
	docker compose down
	$(SUPABASE) stop

migrate: ## Apply pending supabase/migrations to the local database
	$(SUPABASE) migration up

db-reset: ## Recreate the local database from migrations (destroys local data)
	$(SUPABASE) db reset

db-size: ## Report database and per-table size
	$(UV) run --package tracksync-etl python -m tracksync_etl.dbsize

etl: ## Run the ETL, e.g. make etl ARGS="--season 2024 --event 16"
	$(UV) run --package tracksync-etl tracksync-etl $(ARGS)

test: test-py test-web ## All tests

test-py: ## pytest for racemodel, etl, api
	$(UV) run pytest packages/racemodel services/etl services/api

test-web: ## vitest for the web app
	@if [ -f apps/web/package.json ]; then pnpm --filter web test; else echo "web app not scaffolded yet"; fi

e2e: ## Playwright showcase tests (builds from fixtures, no API needed)
	pnpm --filter web e2e:install
	pnpm --filter web e2e

lint: lint-py lint-web ## All linters and type checks

lint-py:
	$(UV) run ruff check .
	$(UV) run ruff format --check .

lint-web:
	@if [ -f apps/web/package.json ]; then pnpm --filter web lint && pnpm --filter web typecheck; else echo "web app not scaffolded yet"; fi

fmt: ## Auto-format Python
	$(UV) run ruff check --fix .
	$(UV) run ruff format .

rag-backfill: ## Embed knowledge-base chunks into the LOCAL DB (once a day until done; decision 0037)
	bash scripts/rag-backfill.sh; tail -n 5 .cache/rag-backfill.log

eval: ## Race-model backtest + chat evals (retrieval always; full agent when LLM keys are set)
	$(UV) run --package tracksync-etl python evals/racemodel/backtest.py
	$(UV) run --package tracksync-api python evals/chat/run_eval.py --check
	$(UV) run --package tracksync-api python evals/chat/run_eval.py $(if $(GROQ_API_KEY)$(GEMINI_API_KEY),--agent,)

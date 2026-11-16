# TrackSync: project guide for Claude Code

TrackSync is an unofficial Formula 1 analytics hub built as an end-to-end portfolio
project (repo: github.com/AchintyaShah25/TrackSync). It was called "Pit Wall" (`pitwall`)
until 2026-11-14; older decision records and test logs use that name (see decisions 0014, 0016). The full plan, data model, and phase checklists live in
`docs/SPEC.md`. Read the relevant milestone there before starting any task.

## What we are building

A small, polished, minimalist F1 hub with three hero features: race analytics
(telemetry comparison, tire strategy timeline, track map), a strategy forecaster (tire
degradation model + Monte Carlo race simulator), and a chat agent (RAG + tool calling).
Plus login, light personalization, and a demo mode so reviewers can try everything
without signing up. The game and leaderboards are v2 backlog items: do not build them
until Milestone 4 is done.

**Prefer polish over breadth.** When choosing between adding a feature and finishing
the loading states, mobile layout, tests, or docs of an existing one, finish the
existing one. If a task looks like it is growing beyond its milestone, stop and ask.

## Architecture rules (do not break these)

1. **FastF1 runs only in `services/etl`.** Never import `fastf1` in `services/api`. The
   API serves precomputed data from Postgres. FastF1 is slow and memory-hungry; the free
   API container cannot afford it.
2. **The race model lives in `packages/racemodel`.** The ETL uses it to *fit* parameters;
   the API uses it to *simulate*. Pure Python + NumPy, no web or DB imports.
3. **Free-tier constraints are design constraints.**
   - API on Render free: sleeps after ~15 min idle, small CPU/RAM, ~5 GB bandwidth/month.
     Keep responses small (paginate, downsample traces), keep memory low, no large ML
     models loaded in the API process.
   - Supabase free: 500 MB database, project pauses after 7 days of inactivity. Store
     aggregates and downsampled traces only, never raw telemetry.
   - LLM free tiers are rate-limited. All LLM calls go through `services/api/app/llm/`
     (OpenAI-compatible client, provider fallback chain, per-user rate limit).
4. **Auth is Supabase Auth.** The frontend signs users in; the API verifies the Supabase
   JWT on protected routes. User-owned tables use row-level security.
5. **Showcase pages are static.** The landing page and example analyses are generated
   at build time so they load instantly while the free API is asleep.

## Repo layout

```
apps/web/              Next.js (App Router, TypeScript) frontend
services/api/          FastAPI backend (REST + chat agent)
services/etl/          OpenF1/Jolpica ingestion + model fitting (Docker, run by CI cron)
packages/racemodel/    Shared Python: degradation fitting + race simulator
supabase/migrations/   SQL migrations: the single source of truth for the schema
evals/                 RAG and race-model evaluation sets and scripts
docs/                  SPEC.md, decisions/ (decision records), test-log/ (test run log)
.github/workflows/     CI, ETL schedule
docker-compose.yml     Local dev stack
```

## Stack

- Python 3.12, `uv` for dependencies, `ruff` (lint + format), `pytest`, Pydantic v2.
- API: FastAPI, SQLAlchemy 2.0 Core (async) + asyncpg. Schema changes only via
  `supabase/migrations`, never ad-hoc.
- ETL: OpenF1 (historical 2023+, free, no login) for laps, stints, telemetry and position;
  FastF1 (latest stable) only for its Jolpica-F1 interface (results, standings, IDs) and
  MultiViewer circuit info. FastF1 livetiming needs a paid F1TV login: see
  `docs/decisions/0004`.
- Frontend: Next.js, TypeScript strict, Tailwind, shadcn/ui, Recharts, TanStack Query.
- Data/auth/vectors: Supabase (Postgres + pgvector + Auth). Local dev uses the Supabase
  CLI local stack (Docker).
- Hosting: web on Vercel (or Cloudflare Pages), API Docker image on Render, ETL on
  GitHub Actions.

## Commands

A root `Makefile` wraps these (created in Milestone 1):

```
make up          # docker compose up: web, api, local supabase
make etl ARGS=   # run ETL container locally, e.g. ARGS="--season 2025 --event 1"
make test        # pytest (api, etl, racemodel) + vitest (web)
make lint        # ruff check + ruff format --check + eslint + tsc --noEmit
make migrate     # apply supabase/migrations to the local stack
make eval        # run RAG + race-model evals
```

## Conventions

- Python: type hints everywhere, Pydantic models for all request/response bodies,
  routers in `services/api/app/routers/`, one module per resource. No business logic in
  routers; put it in `services/api/app/services/`.
- Frontend: server components for read-only data pages; client components only for
  interactivity. All colors, spacing, and radii come from `apps/web/styles/tokens.css`.
  Recharts is the only chart library unless I approve another.
- Tests: every API endpoint gets a test. Tests never hit the network; FastF1 tests use
  small recorded fixtures in `services/etl/tests/fixtures/`.
- Git: small, focused commits with conventional commit messages (`feat:`, `fix:`, ...).
- Env vars: every new variable is added to `.env.example` with a comment. Never commit
  secrets.

## Documentation of tests and decisions (required)

All of this is written as Markdown files inside this repo on my laptop, never only in
chat. Write them as part of the task, not afterwards.

**Decisions** go in `docs/decisions/` as numbered records (`0001-short-title.md`), using
`docs/decisions/0000-template.md`. Write one for every non-trivial choice: a library or
service, a schema design, an algorithm or model choice, a tradeoff forced by free-tier
limits, or a change of plan. Include context, options considered, the decision, and
consequences. Never edit an old decision to reverse it; write a new one that supersedes
it and link both ways. Keep `docs/decisions/README.md` as an index (number, title,
status, date).

**Tests** are documented in two ways:
1. Every test function has a docstring saying what it checks and why it matters.
2. After every test run during a task, append an entry to
   `docs/test-log/YYYY-MM-DD.md` (create the day's file if missing) using the format in
   `docs/test-log/README.md`: what was run, pass/fail counts, any failures with their
   root cause and fix, and tests added or changed.

Before finishing any task, confirm the decision records and test log are up to date.

## Design language

Clean and minimalist: neutral grays, one accent color, generous whitespace, one font
family, first-class dark mode, no decorative gradients or shadows. Team colors (from
the OpenF1 drivers feed, stored per season in `teams.color_hex`) are used only for data series, never for UI chrome.
Every page must work on mobile.

## Legal and branding

Unofficial project. No F1 logos or trademarked marks in branding; footer states it is
not affiliated with Formula 1 or the FIA. RAG sources are limited to FIA regulation
documents, Wikipedia (CC BY-SA, attribute in the UI), and summaries we generate from our
own data. Do not scrape news sites.

## Working agreements

- Start each milestone or large feature in plan mode. Propose the plan; wait for my approval.
- Ask before adding a dependency, service, or paid-tier feature.
- When unsure about a library's API (especially FastF1), check the installed version's
  docs or source instead of guessing.
- Never deploy unless I invoke `/deploy`.
- After finishing a task, tick its checkbox in `docs/SPEC.md`, update "Current phase",
  and make sure the decision records and test log for the task are written.

## Current phase

**Milestone 3: Chat agent, auth, light personalization**: built and tested locally (2026-11-16).
Evals recorded 2026-11-15 (README; decisions 0034-0037). Open: local embeddings backfill
(`make rag-backfill` once a day until 0 left; Gemini free = 1000/day; it re-runs the eval
when done), then `/deploy` (migration 20261117090000; Render/Vercel env vars; a separate
Google Cloud project key for production Gemini; Supabase redirect URLs; GitHub secrets;
the daily `--rag` cron backfills production once ETL_ENABLED is on). Milestones 1-2 shipped 2026-11-15/16.
Live: web https://tracksync-ruddy.vercel.app, API https://tracksync-api.onrender.com (decision 0018).
After a model refit or showcase change, re-record web fixtures and redeploy Vercel without
build cache (decision 0024).

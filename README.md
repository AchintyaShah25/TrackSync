# TrackSync

An unofficial Formula 1 analytics hub covering the 2023 season to the present. It
includes race results and standings, a lap telemetry comparison, tyre strategy timelines,
speed-colored track maps, a strategy forecaster that replays past races with different
pit strategies across 500 simulated races, and a chat assistant that answers rules,
history and stats questions with cited sources. Everything works without an account;
signing in (email magic link) lets you save views and set preferences.

TrackSync is not affiliated with Formula 1, the FIA, or any team.

## Stack

| Part | What it is |
| --- | --- |
| `apps/web` | Next.js (App Router, TypeScript), Tailwind, Recharts, TanStack Query |
| `services/api` | FastAPI read API on Postgres (SQLAlchemy Core, asyncpg) |
| `services/etl` | Ingestion from OpenF1 and Jolpica-F1 (via FastF1), run weekly by GitHub Actions |
| `packages/racemodel` | Tyre-degradation fitting and Monte Carlo race simulator (NumPy only) |
| `supabase/migrations` | The schema, the single source of truth |

The project plan is in [docs/SPEC.md](docs/SPEC.md), and design choices are in
[docs/decisions/](docs/decisions/README.md).

## Chat assistant: how is it checked?

Answers come from four read-only tools: an allow-listed stats query layer over our own data
(the only source of numbers), hybrid search over the FIA regulations, Wikipedia and race
summaries (cited with licences), the strategy simulator, and charts that can only plot data
those tools returned ([decision 0029](docs/decisions/0029-agent-tools-grounded-stats-and-charts.md)).
A 52-question golden set ([evals/chat](evals/chat/results.md)) measures retrieval hit@5,
whether stats questions used the stats tool, and answer correctness. Latest run
(2026-11-15, Groq `openai/gpt-oss-120b`):

| Metric | Score | Target |
|---|---|---|
| Retrieval hit@5 (rules + history) | 84% | 70% |
| Stats answers that used `query_stats` | 100% | 95% |
| Answer correctness (key facts, 51 of 52 answered) | 96% | |

Embeddings cover 982 of 2,543 chunks so far: Gemini's free tier embeds 1,000 texts a day,
so the rest backfill over the next runs ([decision 0034](docs/decisions/0034-gemini-daily-embedding-quota.md)).

## Strategy forecaster: how accurate is it?

The lap-time model is checked by a leave-one-race-out backtest (`make eval`, full results in
[evals/racemodel/results.md](evals/racemodel/results.md)). Settings were tuned on 22 dry
2025 races; the numbers below are for 16 held-out dry 2026 races (13,867 laps):

| Predictor | Lap-time MAE | Stint mean-pace MAE |
| --- | --- | --- |
| Constant pace (driver's early laps) | 1.22 s | 1.03 s |
| Fuel/track trend only | 0.98 s | 0.82 s |
| **TrackSync model** | **0.82 s** | **0.63 s** |

The model is 33% more accurate than constant pace. Its limits are documented in
[decision 0021](docs/decisions/0021-race-simulator-design.md): rivals keep their real race
times, cars do not bunch up behind a safety car, and there is no traffic model.

## Local setup

You need **Docker**, **uv**, **Node 22+**, and **pnpm**. All other tools are installed
inside the repo, under `.tools/`, `.venv/` and `node_modules/`. They include Python 3.12,
the Supabase CLI, and the package caches. Nothing is installed globally, and
`make clean-tools` removes all of it.

```sh
make bootstrap                                  # Python 3.12, venv, node deps, Supabase CLI; creates .env
make db-up && make migrate                      # local Postgres on 127.0.0.1:54322, schema applied
make etl ARGS="--season 2024 --event 16"        # load one race (Monza 2024), 3-5 minutes
make up                                         # Postgres + api (:8000) + web (:3000) in Docker
```

Then open http://localhost:3000/races/2024/16.

To load everything, run one season at a time: `make etl ARGS="--season 2023"`, then 2024,
2025 and the current year. OpenF1 allows 30 requests a minute, so a season takes 60 to 80
minutes the first time. Responses are cached in `.cache/`, so re-runs are fast and change no
rows. The full 2023-to-date backfill uses about 50 MB of database space. The weekly job runs
`--since-days 8`, which also fills in any completed race of the current season that is still
missing data.

To run the app without Docker, use `make db-up`, then
`uv run --package tracksync-api uvicorn app.main:app --reload`, and then `pnpm --filter web dev`.

| Command | What it does |
| --- | --- |
| `make test` | pytest (api, etl, racemodel) + vitest |
| `make e2e` | Playwright tests of the showcase pages, built from fixtures with no API |
| `make lint` | ruff, eslint, `tsc --noEmit` |
| `make db-size` | Database and per-table size |
| `make down` | Stop the containers (the database data is kept) |
| `make help` | List every command |

### Note: local Postgres is reachable from your network

The Supabase CLI publishes Postgres on all interfaces (`0.0.0.0:54322`). It uses the default
`postgres` password, so other devices on the same Wi-Fi can connect while it runs. The CLI
has no option to change this ([decision 0017](docs/decisions/0017-make-up-starts-postgres-only.md)).
Run `make down` on networks you don't trust, or fix it for your machine by doing one of these:

- **Docker Desktop:** Settings → Docker Engine → add `"ip": "127.0.0.1"`. This makes every
  published port default to localhost and affects all Docker projects.
- **macOS firewall:** turn it on and block incoming connections.

## Data and licences

- **Session data** (laps, stints, telemetry, positions, team colors) comes from
  [OpenF1](https://openf1.org), licensed CC BY-NC-SA 4.0.
- **Results, standings and IDs** come from [Jolpica-F1](https://github.com/jolpica/jolpica-f1),
  accessed through [FastF1](https://github.com/theOehrly/Fast-F1).
- **Circuit corner data** comes from MultiViewer, via FastF1.

The database stores only aggregates and downsampled traces, never raw telemetry.

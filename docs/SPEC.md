# TrackSync: project specification

Unofficial F1 analytics hub and portfolio project (formerly the working name "Pit Wall").

## 1. Goals

Ship a small, polished, deployed application at $0/month built around **three hero
features**, each proving a different skill:

1. **Race analytics** (data engineering + frontend): telemetry comparison, tire strategy
   timeline, track map.
2. **Strategy forecaster** (applied ML): tire degradation model + Monte Carlo race
   simulator, with backtest metrics.
3. **Chat agent** (LLM engineering): hybrid RAG + tool calling, with eval scores.

Presentation is a first-class goal: a reviewer should see something impressive within
30 seconds, with no sign-up and no cold-start wait.

### Non-goals for v1

Live timing, the racing game, time-trial leaderboards, race replay animation, seasons
before 2023, paid infrastructure. These live in the v2 backlog (section 8). Do not start
v2 work until Milestone 4 is complete.

## 2. Architecture

```
OpenF1 + Jolpica ──> ETL worker (GitHub Actions cron, Docker) ──> Supabase
                         │  uses packages/racemodel to fit params   (Postgres, pgvector, Auth)
                         ▼                                              ▲
                  circuit outlines, model params, RAG chunks            │
                                                                        │
Next.js web (Vercel) ──> FastAPI (Render, Docker) ──────────────────────┘
   │ static showcase pages     │  uses packages/racemodel to simulate
   │ built at deploy time      └──> LLM provider (Groq / Gemini, fallback chain)
```

- **ETL** runs on a schedule (Monday 06:00 UTC, after race weekends) plus manual
  dispatch. Idempotent: re-running an event upserts, never duplicates. Its regular
  writes also keep the Supabase free project from pausing.
- **API** is stateless; all state is in Postgres.
- **Showcase pages** (landing page and example analyses) are statically generated at
  build time, so they load instantly even while the free API is asleep. The API only
  needs to wake when a visitor starts exploring.
- **Race model** package is shared by ETL (fit) and API (simulate).

## 3. Data model (initial sketch; refine in each milestone's migration)

Reference data
- `seasons(year)`
- `circuits(id, name, country, outline jsonb, corners jsonb, length_m)`
- `events(id, season, round, circuit_id, name, race_start_utc, sessions jsonb)`
- `drivers(id, code, full_name, number)`, `teams(id, name, color_hex, season)`
- `driver_teams(driver_id, team_id, season)`

Session data
- `results(event_id, session, driver_id, position, grid, points, status, time_ms)`
- `laps(event_id, session, driver_id, lap, lap_time_ms, compound, tyre_life, stint,
  position, pit_in, pit_out, track_status, is_accurate)`
- `stints(event_id, driver_id, stint, compound, start_lap, end_lap)`
- `fastest_lap_traces(event_id, session, driver_id, points jsonb)`: downsampled to
  ~300 points with distance, speed, throttle, brake, gear, x, y.

Race model
- `circuit_model_params(circuit_id, season_window, params jsonb, fitted_at, metrics jsonb)`
  holds deg curves per compound, fuel effect, pit loss, safety car probability, pace noise.

RAG
- `rag_documents(id, source, title, url, license)`
- `rag_chunks(id, document_id, content, embedding vector, metadata jsonb)` with HNSW index.

Users (all with RLS: users read/write only their own rows)
- `user_preferences(user_id, theme, units, favorite_driver_id, favorite_team_id,
  home_widgets jsonb, chat_level)`
- `saved_items(user_id, kind, payload jsonb, created_at)`: saved charts and strategies.
- `chat_sessions`, `chat_messages`

**Storage budget:** keep the whole DB well under 400 MB. Traces and embeddings are the
main cost, so downsample and measure (`make db-size`) after each backfill.

## 4. API surface (v1)

Public: `GET /health`, `/seasons`, `/seasons/{y}/events`, `/events/{id}`,
`/events/{id}/results`, `/events/{id}/laps`, `/events/{id}/stints`,
`/events/{id}/traces?drivers=VER,NOR`, `/standings/{y}`, `/circuits/{id}`,
`POST /strategy/simulate`.

Authenticated or guest (demo mode, stricter limits): `POST /chat`.

Authenticated: `GET/PUT /me/preferences`, `/me/saved`.

## 5. Milestones

Each milestone ends deployed and working, with its decision records and test log
written. Do not start the next milestone until the acceptance criteria pass.

### Milestone 1: Foundation and analytics
- [x] Monorepo scaffold matching CLAUDE.md layout; Makefile; `.env.example`
- [x] `docker-compose.yml`: web, api, Supabase CLI local stack
- [x] Migrations: reference tables, results, laps, stints, traces, circuits
- [x] ETL for seasons 2023 onward: schedule, results, laps, stints, downsampled
      fastest-lap traces; idempotent upserts; CLI args `--season`, `--event`
- [x] Circuit outlines built from the X/Y coordinates in OpenF1 position data: take a
      clean fastest lap, apply the circuit's rotation from FastF1 circuit info (MultiViewer),
      normalize, smooth and simplify to ~300-500 points, store in `circuits.outline`;
      store corner positions for labels
- [x] API: health, seasons, events, results, standings, laps, stints, traces, circuits
- [x] Web pages: season results and standings; telemetry comparison (overlay two
      drivers: speed, throttle, brake, gear); tire strategy timeline; track map
      colored by speed; shareable URLs for every chart state
- [x] Landing page with next-race countdown (viewer's local time) and 3-4 example
      links (e.g. "Compare Verstappen vs Norris at Monza"), statically generated
- [x] Design tokens, dark mode, mobile layouts, "unofficial" footer
- [x] CI: lint + tests on every PR; ETL workflow with schedule + manual dispatch
- [x] Deploy: Supabase project, API on Render, web on Vercel

Acceptance: landing and example pages load instantly with the API asleep; re-running
the ETL on an event changes no row counts; charts load in < 2 s on a warm API; CI green.

### Milestone 2: Strategy forecaster (signature feature)
- [ ] `packages/racemodel`: lap time = base pace + deg(compound, tyre age) + fuel
      effect + track evolution + noise; pit loss added on stop laps
- [ ] Fitting in ETL per circuit: exclude lap 1, in/out laps, SC/VSC laps (track
      status), and outliers; shrink sparse circuits toward global priors
- [ ] Safety car probability per circuit from history; pit loss = median pit delta
- [ ] Monte Carlo simulator (vectorized NumPy, ~500 runs default); randomize SC timing,
      pit stop duration, pace noise
- [ ] `POST /strategy/simulate`: driver, event, list of stints; returns finish time
      distribution, gap-to-baseline per lap, P(gaining positions)
- [ ] UI: build up to 3 strategies and compare them; the **outcome fan chart** (spread
      of simulated results, strategies overlaid) is the project's signature visual and
      gets extra polish; overlay the real strategy for past races
- [ ] Static example page, e.g. "Would a one-stop have won Silverstone?"
- [ ] Backtest on held-out races; record stint lap-time MAE in `evals/` and README

Acceptance: backtest metrics recorded; simulation responses under 1.5 s cold-cache.

### Milestone 3: Chat agent, auth, light personalization
- [ ] LLM client: OpenAI-compatible, provider fallback chain, timeouts, rate limits
- [ ] RAG ingestion in ETL: FIA regulations, Wikipedia season/race articles (store
      license + URL), generated race summaries from our data; chunk + embed into pgvector
- [ ] Agent tools: `search_knowledge`, `query_stats` (fixed parameterized queries only),
      `simulate_strategy`, `make_chart` (returns a chart spec the frontend renders)
- [ ] Chat UI with source citations and inline charts; suggested starter questions
- [ ] Evals: golden set of ~50 questions (rules, history, stats); measure retrieval hit
      rate and answer correctness; run in CI; record scores in README
- [ ] Supabase Auth (Google OAuth + email magic link); API JWT verification
- [ ] Preferences with RLS: favorite driver/team, theme, units, chat level, pinned home
      widgets; saved charts and strategies
- [ ] Demo mode: every feature usable without sign-up (guest chat with a stricter
      rate limit); sign-in only needed to save things
- [ ] Optional, only if ahead of schedule: race prediction leaderboard (predict podium
      + fastest lap before lights out, scored automatically after the ETL ingests results)

Acceptance: eval scores recorded; stats answers come from `query_stats`, not retrieval;
a user cannot read another user's rows (RLS test); a guest can try every hero feature.

### Milestone 4: Polish and ship
- [ ] README as a case study: one-line pitch, live link, 60-90 s demo video or GIF,
      architecture diagram, 3-4 key design decisions linking to `docs/decisions/`,
      headline metrics (section 6), local setup in a few commands
- [ ] "How it's built" page on the site: architecture diagram and key tradeoffs
- [ ] Structured logging, basic error tracking, slow-query review
- [ ] Accessibility pass (keyboard nav, contrast, chart text summaries), Lighthouse pass
- [ ] Draft a short write-up post on building the strategy simulator, using the fan chart
- [ ] Draft resume bullets from the metrics and decision records

Acceptance: a first-time visitor reaches an impressive chart in one click; README and
"How it's built" page are complete. Then stop and ship.

## 6. Headline metrics (measure and report)

- Chat agent: answer accuracy and retrieval hit rate on the eval set
- Strategy forecaster: stint lap-time MAE on held-out races
- Performance: p95 API latency on warm requests; static page load time
- Engineering: test count and CI status badge

## 7. Security and free-tier budget

Security: JWT verification on `/me/*` and authenticated routes; RLS on every user-owned
table; service role key only in ETL and API secrets; rate limits on chat and simulate
(stricter for guests); CORS restricted to the web origin; `query_stats` uses
allow-listed parameterized queries only.

| Resource | Limit to respect | Strategy |
|---|---|---|
| Supabase DB | 500 MB | Aggregates + downsampled traces; 2023+ only; measure after backfills |
| Supabase activity | Pauses after 7 idle days | Weekly ETL writes |
| Render bandwidth | ~5 GB/month | Small JSON, gzip, client caching, static showcase pages |
| Render cold start | Sleeps after ~15 min | Static showcase pages; loading states |
| LLM quota | Per-model RPM/RPD caps | Fallback chain, per-user and guest limits, short prompts |

Free-tier limits change often; re-check provider pricing pages before each milestone.

## 8. v2 backlog (do not start before Milestone 4 is done)

- Race prediction leaderboard (if not done in Milestone 3)
- Browser racing game: top-down Canvas 2D on the real X/Y circuit outlines from
  Milestone 1, arcade physics, keyboard + touch controls, ghost of the real pole lap
- Race-week time-trial leaderboard with server-side lap validation (checkpoints,
  plausible segment times, rate limits), freezing when the race ends, hall of fame
- Race replay animation on the track map
- Backfill seasons 2018-2022; extra charts (position chart, lap time distribution,
  teammate head-to-head)

## 9. Open decisions

- ~~Final project name~~: **TrackSync** (decided 2026-11-14, decision 0014); domain still open
- Embeddings: small local model vs a free embedding API (API RAM is tight)
- Which three or four example analyses to feature on the landing page

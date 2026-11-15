# 0024: Forecast page: static POST example, strategy colours, URL state

- **Status:** Accepted
- **Date:** 2026-11-16
- **Milestone:** 2

## Context
The forecast page (`/races/[year]/[round]/forecast`) is the signature feature, and three
design questions came up while building it:
1. **Static example.** The showcase example ("Would a one-stop have won Monza for
   Piastri?") must load instantly while the free API sleeps (CLAUDE.md rule 5). The
   simulator is a POST, but build-time fixtures (decision 0010) only recorded GETs, keyed
   by path.
2. **Colours.** All strategies belong to one driver, so team colours (the data-series rule)
   can't tell them apart.
3. **Sharing and API cost.** Forecasts should be shareable, but every run costs a
   rate-limited API call.

## Options considered
- **Static example:**
  - Add a GET endpoint for a precomputed example, which means special-case API code.
  - Precompute JSON into the repo, which goes stale when the model is refit.
  - **Chosen:** record POST responses keyed by path + a hash of the request body.
- **Colours:**
  - Reuse tyre colours, which would clash with the stint chips.
  - Reuse the accent, which is reserved for UI chrome.
  - **Chosen:** three dedicated strategy tokens.
- **When to simulate:** on every edit (too many calls), only on a button press (an empty
  page at first), or **auto-run the applied strategies and use a button for edits**.

## Decision
- **POST fixtures:** `serverPostOrNull()` (`lib/api/server.ts`) records and replays POST
  responses as `strategy_simulate_<sha256-12>.json`. A showcase forecast is rendered at
  build time with a fixed seed, and the client's query sees the identical request as
  `initialData`, so no API call happens.
- **Colours:** `--chart-strategy-1..3` (blue, burnt orange, violet) with dark-mode variants,
  plus `--chart-neutral-band` for safety-car shading. Band opacities (0.14 outer, 0.30
  inner) are constants in `lib/charts/forecast.ts`, since the tokens only cover colours,
  spacing and radii.
- **URL state:** the applied strategies live in the URL (`d=PIA&s1=M15-H38&s2=M21-H32&sc=actual`).
  The page simulates whatever the URL says, with a fixed seed (7) and 500 runs, so a shared
  link reproduces the same forecast, and repeat visits hit TanStack Query's cache
  (`staleTime: Infinity`). Edits happen in a draft and run only on "Simulate".
- **Validation:** strategies are checked in the browser with the same rules as the API, so
  an illegal or short strategy is blocked before any call (user decision: block, don't warn).
- **Empty states without an API call:** future races (no laps), wet races (the stints feed,
  same 10% rule as the API) and circuits without a fitted model each show an empty state
  instead of attempting a simulation.

## Consequences
- **Fixtures go stale:** changing the showcase strategies, the seed or the model changes
  the body hash or the response. Re-record fixtures (fixtures/README.md) after a refit,
  or CI builds the example without its forecast.
- **The fan chart plots time ahead of the real strategy** (positive = better). The API
  reports the gap the other way round (positive = behind), and `fanRows()` flips it; a
  unit test guards the sign.
- **The Segmented control no longer shrinks or wraps.** That changes every page that uses
  it, but only cosmetically.

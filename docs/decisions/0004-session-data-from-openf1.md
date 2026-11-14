# 0004: Session data from OpenF1; FastF1 kept only for Jolpica and circuit info

- **Status:** Accepted
- **Date:** 2026-11-14
- **Milestone:** 1
- **Refines:** [0001](0001-decouple-etl-from-api.md) (the ETL/API split is unchanged)

## Context
The plan used FastF1 for laps, tire compounds, telemetry and X/Y position. FastF1 3.9.2
fetches these from `livetiming.formula1.com`, which now returns **401 without an F1TV
subscription token** (checked 2026-11-14 with a direct request and with
`Session.load()`, which logs "Car telemetry data is unavailable"). A paid
subscription breaks the $0/month goal and would tie the CI ETL to a personal account.
Still free: Jolpica (schedule, results, standings, Jolpica IDs) and the MultiViewer
circuit API that `fastf1.mvapi` wraps (rotation, corners).

## Options considered
1. **FastF1 with the owner's F1TV login**: no code changes, but paid, personal
   credentials in CI, and unclear terms for automated use.
2. **OpenF1 for session data + Jolpica + MultiViewer**: OpenF1 historical data (2023
   onward, exactly our scope) needs no login. It provides `laps`, `stints` (compound, tyre
   age), `car_data` (~3.7 Hz speed/throttle/brake/gear), `location` (X/Y), `race_control`,
   `pit`, `drivers`, `sessions`. Free tier: 3 req/s and 30 req/min. License: CC BY-NC-SA 4.0,
   non-commercial; credit optional.
3. **Pluggable source, both of the above**: more code and tests for the same output.

## Decision
Option 2. `services/etl` gets an OpenF1 client (rate limited to under 30 req/min, retry on
429/5xx, raw responses cached on disk under `OPENF1_CACHE_DIR`). FastF1 stays a
dependency of the ETL only for `fastf1.ergast` (Jolpica) and `fastf1.mvapi` (circuit
rotation and corners). Architecture rule 1 still holds: no FastF1 in the API.

## Consequences
- The schema is unchanged. Fields OpenF1 lacks are derived:
  - `laps.track_status`: from `race_control` SC/VSC/red-flag windows over each lap's time span
  - `laps.pit_in`: the lap before a `pit` entry
  - `laps.position`: from `position` samples at lap end
  - `laps.is_accurate`: lap duration present, not an in/out lap, not lap 1
- Telemetry is ~3.7 Hz (about 300 samples on a 80 s lap), so the 300-point trace grid is
  close to native resolution. Peak speeds may be slightly under-read.
- About 95 requests per event means a full backfill takes ~5 h. It runs per season
  (~80 min each, within the 6 h GitHub Actions job limit). The disk cache makes re-runs free.
- Non-commercial license: fine for a portfolio project. The site footer credits OpenF1 and
  Jolpica. If this ever became commercial, the data source would need revisiting.
- Revisit if FastF1 regains anonymous access or a subscription becomes acceptable.

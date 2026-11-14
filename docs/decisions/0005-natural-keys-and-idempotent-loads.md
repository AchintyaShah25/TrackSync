# 0005: Natural keys and idempotent loads

- **Status:** Accepted
- **Date:** 2026-11-14
- **Milestone:** 1

## Context
Acceptance requires that re-running the ETL on an event changes no row counts. The ETL
also runs weekly on a cron and may be re-run by hand after source data is corrected.
Three sources must be joined: Jolpica (results, IDs), OpenF1 (keyed by car number and
session_key), and MultiViewer (keyed by circuit_key).

## Options considered
1. **Surrogate serial ids + lookup tables**: flexible, but every load needs lookups
   and a re-run risks duplicates if a lookup misses.
2. **Deterministic natural keys**: `events.id = season*100 + round`, Jolpica `driverId`
   / `constructorId` / `circuitId` as text keys, composite PKs on session tables.
3. **Source keys from OpenF1** (session_key, driver_number): car numbers change between
   seasons (e.g. #1 for the champion), and OpenF1 has no stable driver id.

## Decision
Option 2. Loads are idempotent by construction:
- Reference tables are upserted on their primary key. Circuit columns from the schedule
  never overwrite the derived outline.
- Event-scoped tables (results, laps, stints, traces) are delete-then-insert per
  `(event_id, session)` in one transaction, so stale rows from a corrected source cannot
  linger.
OpenF1 rows join to Jolpica ids through the car number raced in that event
(`results.number_to_driver`). OpenF1 meetings are matched to Jolpica rounds by race date.

## Consequences
- Re-runs are safe and cheap (with the response cache, they make no API calls).
- `events.id` is human-readable (202416 = 2024 round 16) and makes URLs simple.
- If Jolpica ever renamed an id, rows would split. This is unlikely, since Ergast ids
  have been stable for years.
- A driver in OpenF1 but missing from Jolpica (rare data lag) is skipped until a later run.

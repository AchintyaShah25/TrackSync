# 0001: Decouple FastF1 ETL from the API

- **Status:** Accepted
- **Date:** 2026-11-14
- **Milestone:** 1

## Context
FastF1 downloads and processes large amounts of session data and uses a lot of memory.
The API runs on a free container with little CPU and RAM that sleeps when idle.

## Options considered
1. **Call FastF1 inside API requests** (with a disk cache): simple, but slow cold
   requests, high memory, and the free container's disk is not persistent.
2. **Separate ETL worker on a schedule** writing precomputed data to Postgres: more
   moving parts, but fast, predictable API responses within free-tier limits.

## Decision
Option 2. FastF1 runs only in `services/etl`, triggered by a GitHub Actions cron and
manual dispatch. The API reads only from Postgres.

## Consequences
Data appears after the ETL runs, not instantly after a session. The API stays light and
fast. The weekly ETL writes also keep the free Supabase project active.

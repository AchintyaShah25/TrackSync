# 0012: Local dev stack: Supabase CLI containers + compose for app services

- **Status:** Accepted (`make up` amended by [0017](0017-make-up-starts-postgres-only.md))
- **Date:** 2026-11-14
- **Milestone:** 1

## Context
SPEC asks for a `docker-compose.yml` with web, api and a local Supabase stack. The Supabase
CLI manages its own set of containers and cannot be embedded in a compose file cleanly.

## Options considered
1. **Hand-written compose file replicating Supabase services**: fragile, and drifts from
   hosted Supabase.
2. **Supabase CLI for the database stack, compose for api/web**: the officially supported
   local stack, with app containers talking to it over the host network.

## Decision
Option 2. `make db-up` / `make up` start the CLI stack (`supabase db start` / `supabase
start`, project id `pitwall`). Containers reach Postgres at `host.docker.internal:54322`.
Migrations in `supabase/migrations` are the only schema source and are applied by
`make migrate` / `make db-reset`.

## Consequences
- The local schema matches hosted Supabase exactly, including the `anon`/`authenticated`
  roles used by RLS.
- Known issue: the CLI binds Postgres to `0.0.0.0:54322` with the default password, so it is
  reachable from the local network while running. Stop it (`make down`) on untrusted networks.

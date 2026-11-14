# 0013: Tests use throwaway databases on the local Supabase Postgres

- **Status:** Accepted
- **Date:** 2026-11-14
- **Milestone:** 1

## Context
CLAUDE.md: every endpoint gets a test, and tests never hit the network. The ETL's
idempotency criterion can only be proven against real Postgres semantics (`ON CONFLICT`,
jsonb, composite keys, RLS policies referencing Supabase roles).

## Options considered
1. **SQLite or mocks**: fast, but none of the Postgres behavior we rely on.
2. **testcontainers**: isolated, but a new dependency and slow container start per run.
3. **Fresh databases on the already-running local Supabase Postgres**: the root
   `conftest.py` exposes `fresh_database(name)`, which drops and recreates the database,
   applies every migration, and is used as `pitwall_test_etl` / `pitwall_test_api`.

## Decision
Option 3. Tests needing a DB are marked `db` and skip when Postgres is not running. CI runs
`supabase db start` before pytest.

## Consequences
- The full Python suite runs in ~15 s against real Postgres, and the ETL and API suites
  cannot interfere with each other.
- Developers need `make db-up` for the DB tests. Without it those tests are skipped, not
  failed (CI will still run them).

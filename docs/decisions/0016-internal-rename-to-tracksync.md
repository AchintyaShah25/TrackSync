# 0016: Internal identifiers renamed from `pitwall` to `tracksync`

- **Status:** Accepted
- **Date:** 2026-11-14
- **Milestone:** 1
- **Supersedes:** the "internals keep `pitwall`" part of [0014](0014-project-name-tracksync.md)

## Context
0014 kept the internal `pitwall` names while the backfill was writing to the local
database. The backfill has finished (90/90 completed events), and the owner asked for the
rename.

## Options considered
1. **Keep `pitwall` internally**: no work, but two names forever.
2. **Rename now, preserving local data with a dump/restore**: one name everywhere, with
   no re-backfill.

## Decision
Option 2. Renamed:
- the package `pitwall_etl` → `tracksync_etl`, and the projects `pitwall-etl`/`pitwall-api`
  → `tracksync-etl`/`tracksync-api` (CLI `tracksync-etl`)
- the root project `tracksync`, the Supabase `project_id = "tracksync"`, and the test
  databases `tracksync_test_*`
- everything that refers to these: Makefile, Dockerfiles, workflows, tests
- a regenerated `uv.lock`, and a recreated `.venv` (prompt `tracksync`)

Local data was moved with `pg_dump --data-only` → `pg_restore` into the new stack; all ten
table row counts matched, and the `etl_runs` identity sequence was intact. The old Docker
volume and images were then removed.

## Consequences
- One name everywhere except historical records: decision records and test logs written
  before this keep "pitwall" on purpose, since they describe what was true then.
- The repo folder stays `~/Desktop/TrackSync.nosync` (decision 0015).

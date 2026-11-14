# 0014: Project name TrackSync; internal identifiers keep `pitwall` for now

- **Status:** Accepted
- **Date:** 2026-11-14
- **Milestone:** 1

## Context
"Pit Wall" was a working name (SPEC §9 open decision). The owner chose **TrackSync** and
created the GitHub repo `AchintyaShah25/TrackSync` (private). The codebase uses
`pitwall` in internal identifiers: the Python packages (`pitwall_etl`, `pitwall-api`), the
`pitwall-etl` CLI, the Supabase local project id (container names such as
`supabase_db_pitwall`), test database names, and the folder `~/Developer/pitwall`. A
multi-hour backfill was writing to the local database at the time.

## Options considered
1. **Rename everything now**: consistent, but it recreates the local Supabase containers
   mid-backfill and changes import paths across ETL, tests and Dockerfiles.
2. **Rename everything user-visible now; internals later or never**: the brand is right
   wherever a visitor or reviewer looks (site, titles, footer, API docs title, README,
   User-Agent), and nothing running breaks.

## Decision
Option 2. User-facing strings, docs (CLAUDE.md, SPEC), the compose project name, the
favicon and the OpenF1 User-Agent say TrackSync. Internal `pitwall` identifiers stay
until the backfill is done; a later rename is optional and mechanical.

## Consequences
- Reviewers see TrackSync everywhere they look; `pitwall` appears only in code paths.
- If the internals are renamed later: rename the packages and CLI, update the Dockerfiles
  and `.github/workflows`, change `project_id` in `supabase/config.toml` (recreates local
  containers, so re-run the backfill from cache), and move the folder (then re-run
  `make bootstrap`).
- No trademark search was done for "TrackSync"; worth a quick check before buying a domain.

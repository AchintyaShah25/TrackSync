# 0037: Embedding backfill: daily GitHub Actions run for production, manual locally

- **Status:** Accepted
- **Date:** 2026-11-15
- **Milestone:** 3

## Context
Gemini embeds 1000 texts a day for free (0034), and the knowledge base has about 2,543
chunks. A full build therefore takes about three days of runs, and so does any later
backlog. The owner asked for the run to be automated.

A macOS launchd job was built and tested. It failed with "Operation not permitted": macOS
privacy protection (TCC) blocks background jobs from reading `~/Desktop`, where the repo
lives (`~/Desktop/TrackSync.nosync`).

## Options considered
1. **Move the repo out of `~/Desktop`:** launchd would then work with no extra permission,
   but the repo path changes.
2. **Give `/bin/bash` Full Disk Access:** one setting, but any background bash script
   could then read every protected folder.
3. **No local schedule:** production backfills on GitHub Actions; the local database is
   backfilled by hand with `make rag-backfill`.

## Decision
Option 3, the owner's choice.
- **Production:** the ETL workflow gets a daily cron at 09:30 UTC that runs
  `tracksync-etl --rag`, after Gemini's quota resets at midnight Pacific. Like the
  weekly ETL it runs only when `ETL_ENABLED` is true. Once everything is embedded, a run
  makes no embedding requests and takes about a minute.
- **Local:** `make rag-backfill` (`scripts/rag-backfill.sh`), run once a day until it
  reports 0 left. It always targets the local database, whatever `.env` says, and logs
  to `.cache/rag-backfill.log`. When every chunk is embedded, it re-runs the chat eval
  once (keeping earlier answers) so the README scores reflect full hybrid retrieval.

## Consequences
- **The quota is per Google Cloud project, not per key.** Production's daily run,
  production chat questions and local backfills share one quota if they use the same
  project. Give production a key from a separate Google Cloud project at `/deploy`.
- **Local embeddings need a person to run the backfill.** Search works without vectors
  (full-text fallback, 0027), so nothing breaks if a day is missed.
- **Revisit** if the repo moves out of `~/Desktop`: the launchd approach (a plist plus a
  `make` target) worked apart from the folder permission.

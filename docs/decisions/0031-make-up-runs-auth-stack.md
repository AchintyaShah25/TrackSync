# 0031: `make up` runs the Supabase stack minus unused services

- **Status:** Accepted (supersedes the `make up` part of [0017](0017-make-up-starts-postgres-only.md))
- **Date:** 2026-11-16
- **Milestone:** 3

## Context
Decision 0017 started only Postgres locally until auth arrived. Sign-in (decision 0030)
needs Supabase Auth, its gateway, and a way to read magic-link emails locally.

## Decision
- **`make stack-up`** runs `supabase start` excluding realtime, storage-api, imgproxy,
  postgrest, postgres-meta, studio, edge-runtime, logflare, vector and supavisor. What
  remains is Postgres, GoTrue (Auth), Kong (gateway) and Mailpit, where magic-link
  emails can be read at http://127.0.0.1:54324.
- **`make up`** now uses it. `make db-up` still starts Postgres alone for tests.
- **Redirects:** `supabase/config.toml` allows `/auth/callback` on 127.0.0.1:3000 and
  localhost:3000.
- **Compose:** passes `SUPABASE_URL`, the anon key and the LLM keys from `.env` to the
  containers.

## Consequences
- The first `make up` downloads three more images.
- The CI and test paths are unchanged (`db start` plus throwaway databases, decision 0013).

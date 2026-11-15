# 0017: `make up` starts only Postgres until auth lands

- **Status:** Accepted (amends the `make up` part of 0012); superseded in part by [0031](0031-make-up-runs-auth-stack.md)
- **Date:** 2026-11-15
- **Milestone:** 1

## Context
Decision [0012](0012-local-dev-stack.md) had `make up` run `supabase start`, which pulls and
runs the whole Supabase stack: Auth, PostgREST, Kong, Realtime, Storage, Studio, edge
runtime, Logflare, Vector, Mailpit and Supavisor. Milestones 1 and 2 use only Postgres. Auth
is a Milestone 3 task (SPEC §7), and the app never calls PostgREST. The extra containers cost
several GB of images and a few GB of RAM on a laptop, and they add start-up time and failure
points without exercising any of our code.

While verifying `docker compose up` end to end (2026-11-15) we also confirmed the known
issue noted in 0012. The CLI publishes Postgres on all interfaces (`0.0.0.0:54322`), and
the default password is reachable from the LAN IP. Neither `supabase/config.toml` nor the
`db start`/`start` flags of CLI 3.1.0 can set a bind address.

## Options considered
1. **Keep `supabase start`**: matches hosted Supabase fully, but it is heavy and unused until M3.
2. **`supabase start -x <everything except Postgres>`**: works, but the exclude list is long
   and drifts as the CLI adds services.
3. **`make up` = `db-up` + `migrate` + `docker compose up --build`**: starts only what the app
   uses, and re-applies pending migrations on every start.

## Decision
Option 3. When Supabase Auth is added in Milestone 3, `make up` switches back to
`supabase start`, excluding the services we still do not use, and a new record notes the change.

## Consequences
- `make up` starts Postgres, api and web, and nothing else. Verified: all pages return 200
  through the containers, and hot reload picks up new and edited files.
- Local Studio is not available by default; `pnpm exec supabase start` still works for
  anyone who wants it.
- The LAN exposure of port 54322 remains. Machine-level fixes (Docker Desktop's default bind
  address, or the macOS firewall) are outside the repo and left to the developer; the
  README documents them. Stop the stack with `make down` on untrusted networks.

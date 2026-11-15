# 0018: Production hosting setup and connection routing

- **Status:** Accepted
- **Date:** 2026-11-15
- **Milestone:** 1

## Context
The first production deploy needs a hosted Supabase project, the API on Render free and
the web app on Vercel (SPEC §2). Three facts shape how they connect:

- The Supabase direct host `db.<ref>.supabase.co` resolves only to IPv6. Render and
  GitHub Actions runners have no IPv6 egress, and neither does the developer laptop's
  network, so the direct host is unreachable from all three.
- Supabase free caps connections, and Render free has little RAM.
- The showcase pages are generated at build time from the API (CLAUDE.md rule 5), so the
  Vercel build needs a live API with data behind it.

## Options considered
1. **Configure Render by hand in the dashboard**: nothing to maintain in git, but the
   settings (Dockerfile path, build context, health check, region) are invisible and easy
   to get wrong when recreating the service.
2. **Render Blueprint (`render.yaml`)**: the service definition lives in the repo; secrets
   stay out of git through `sync: false`. Costs one small file.
3. **Pay for the Supabase IPv4 add-on** to use the direct host: not allowed (free tier).

For the database route: the transaction pooler (port 6543) multiplexes many clients onto
few server connections but breaks prepared statements; the session pooler (port 5432)
behaves like a normal connection but holds one server connection per client.

## Decision
Use a Render Blueprint (`render.yaml`) in region Virginia, next to the Supabase project in
AWS us-east-1. Auto-deploy only after CI checks pass.

The API connects through the **transaction pooler** (`aws-0-us-east-1.pooler.supabase.com:6543`).
This is safe because `services/api/app/db.py` already disables asyncpg statement caches.
The ETL (GitHub secret `ETL_DATABASE_URL`) and `supabase db push` from the laptop use the
**session pooler** on port 5432, because migrations and bulk upserts want a normal session.

Order for a fresh environment: migrations, then load data, then the API, then the Vercel
import, so the first static build has data to render.

## Consequences
- Recreating the API is "New → Blueprint" plus two pasted secrets.
- `supabase db push` works without `supabase login` via `--db-url` (the CLI calls it
  `--remote` from v4). The CLI access token is only needed for project management commands.
- `WEB_ORIGIN` must be updated on Render once the Vercel URL is known, or browser calls
  from the site fail CORS.
- If we move to a paid Supabase tier with IPv4, the direct host becomes an option for
  the ETL, but the pooler stays the better choice for the API.

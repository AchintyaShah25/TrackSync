---
name: new-api-endpoint
description: Use when adding or changing a FastAPI endpoint in services/api. Covers router, schema, service layer, migration check, auth, and tests.
---

# Adding an API endpoint

Follow these steps in order.

1. **Schema first.** Define request/response Pydantic v2 models in
   `services/api/app/schemas/<resource>.py`. Responses must be small: paginate lists
   (`limit`, `cursor`) and never return raw telemetry.
2. **Data.** If the endpoint needs new tables or columns, add a SQL migration in
   `supabase/migrations/` (timestamped filename). Never alter the schema from Python.
   User-owned tables need an RLS policy in the same migration.
3. **Service layer.** Put queries and logic in `services/api/app/services/<resource>.py`
   using SQLAlchemy Core (async). No `fastf1` imports, ever.
4. **Router.** Add the route in `services/api/app/routers/<resource>.py`; keep it thin.
   Protected routes depend on `get_current_user` (Supabase JWT). Rate-limited routes
   (chat, simulate, submissions) use the shared limiter dependency.
5. **Caching.** Read-only public data gets `Cache-Control` headers suited to how often
   the ETL updates it.
6. **Tests.** Add `services/api/tests/test_<resource>.py` covering success, validation
   errors, auth failure (if protected), and empty results. No network calls.
7. **Docs.** Add the route to section 4 of `docs/SPEC.md` if it is new.

Finish by running `make lint` and `make test`.

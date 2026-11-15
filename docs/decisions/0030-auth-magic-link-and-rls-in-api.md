# 0030: Sign-in with magic links; the API checks tokens with Supabase; RLS inside the API

- **Status:** Accepted
- **Date:** 2026-11-16
- **Milestone:** 3

## Context
- Sign-in is optional and only needed to save things (demo mode).
- The owner chose magic links only for now (no Google OAuth setup).
- Approved dependency: `@supabase/supabase-js` (web). Nothing new for the API.
- The project signs tokens with ES256; verifying them locally would need a crypto
  library.
- Showcase pages must stay static.

## Options considered
- **Browser:**
  - `@supabase/ssr` with a Next 16 `proxy.ts` that refreshes cookie sessions on every
    request.
  - **Chosen:** supabase-js only, in the browser, with the PKCE flow.
- **API token check:**
  - PyJWT with the JWKS keys (a new dependency).
  - **Chosen:** `GET /auth/v1/user`, cached for 5 min per token hash.
- **User-data access:**
  - The API filters by `user_id` itself.
  - **Chosen:** the API runs `/me` queries as `authenticated` with the JWT claims, so
    Postgres row-level security enforces ownership.

## Decision
- **Browser:**
  - `lib/auth/supabase.ts` creates the client only when `NEXT_PUBLIC_SUPABASE_URL` and the
    anon key are set; otherwise the sign-in UI is hidden.
  - `/login` sends the magic link.
  - `/auth/callback` exchanges the PKCE code, and post-login redirects are restricted to
    same-site paths.
  - Nothing personal is rendered on the server, and there is no proxy, so pages stay
    static and Vercel does no per-request work.
- **API:**
  - `optional_user` (chat) and `current_user` (`/me`) dependencies read the bearer token.
  - A present but invalid token is a 401, so the browser refreshes instead of being
    silently downgraded to guest.
  - An auth-server outage is a 503.
- **`/me` routes:**
  - Each request runs in its own transaction with `set local role authenticated` and
    `set_config('request.jwt.claims', …, true)`, exactly as Supabase's REST layer does.
  - Verified on production through the transaction pooler: the role reverts after the
    transaction.
  - Public reference checks (does this driver exist?) run as the service, before the
    role switch.
- **Tables:**
  - `user_preferences` and `saved_items` have `for all to authenticated` policies on
    `auth.uid() = user_id`.
  - Anon access is revoked.
  - Saved paths must be site-relative (a CHECK constraint plus API validation).
  - Up to 100 saved items and 6 pinned per user.

## Consequences
- Isolation is tested both in SQL (test_rls.py) and through the API (test_me.py).
- Adding Google sign-in later needs only a button and the dashboard configuration.
- Each signed-in request costs one cached call to Supabase Auth every 5 minutes.

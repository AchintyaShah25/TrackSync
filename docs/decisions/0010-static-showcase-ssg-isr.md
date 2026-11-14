# 0010: Static showcase pages with build-time generation and daily ISR

- **Status:** Accepted
- **Date:** 2026-11-14
- **Milestone:** 1

## Context
A reviewer must see something impressive within 30 seconds, but the free Render API sleeps
after ~15 minutes and takes up to a minute to wake. CLAUDE.md rule 5 requires the landing
page and example analyses to load instantly while the API is asleep. Next.js 16 offers both
classic ISR (`export const revalidate`) and the opt-in Cache Components model (`'use cache'`).

## Options considered
1. **Client-only fetching**: simple, but every first visit shows a spinner while the API wakes.
2. **Cache Components (`cacheComponents: true`, `'use cache'` + `cacheLife('days')`)**: the new
   model, but it is a newer, stricter model (route segment configs error), and it gains
   little for pages that change weekly.
3. **Classic SSG + ISR**: pages fetch in server components with `next.revalidate = 86400`;
   showcase routes are listed in `generateStaticParams`; other races render on first
   request and are then cached (`dynamicParams` default).

## Decision
Option 3. Showcase presets live in `apps/web/lib/showcase.ts`. Showcase routes are built
at deploy time with their exact selections (e.g. VER vs NOR at Monza). Their data reaches
the client charts as TanStack Query `initialData`, so they render with no API call. Client
views read the URL (inside `<Suspense>`, as Next 16 requires for `useSearchParams`) and
fetch only when it differs from the defaults. Build-time fetches retry for about a minute
to wake the API. CI builds use snapshots via `SHOWCASE_FIXTURES=1`.

## Consequences
- Showcase pages are instant and survive API downtime; stale pages keep serving if a
  revalidation fails.
- Non-showcase races load instantly after their first visit. The first visitor of a race
  may wait for the API to wake, with skeleton states shown meanwhile.
- The landing countdown embeds the season schedule and picks the next race on the client,
  so it never goes stale between rebuilds.

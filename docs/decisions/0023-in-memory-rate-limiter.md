# 0023: In-memory rate limiter for the simulator, no new dependency

- **Status:** Accepted
- **Date:** 2026-11-16
- **Milestone:** 2

## Context
SPEC §7 requires rate limits on `POST /strategy/simulate`. A simulation is cheap (15–80
ms), but the API runs as one uvicorn worker on Render's free instance, so a burst of
requests could still starve other users. Things to work with:
- **No shared store:** there's no Redis.
- **Proxy:** requests arrive through Render's proxy, which sets `X-Forwarded-For`.
- **Dependencies:** CLAUDE.md asks for approval before adding a dependency.

## Options considered
1. **slowapi / limits:** a known library, but it's a new dependency, and with one worker
   its storage backend adds nothing.
2. **Redis or Upstash token bucket:** correct across workers, but it's another service
   (and a free tier to watch) we don't need with one worker.
3. **Hand-written in-memory token buckets:** about 60 lines, unit-tested, no dependency.

## Decision
Option 3 (`services/api/app/ratelimit.py`).
- **Per-client bucket:** 10 simulations a minute (burst 10), keyed by the first
  `X-Forwarded-For` hop, falling back to the socket address.
- **Global bucket:** 120 a minute across all clients. A client can spoof the forwarded
  header to dodge its own bucket, but not this one, so it is the hard CPU cap.
- **Configuration:** both limits come from `SIMULATE_PER_MINUTE` and
  `SIMULATE_GLOBAL_PER_MINUTE`.
- **When limited:** `429` with `Retry-After`. The web app shows "try again in N s".
- **Memory:** buckets are pruned once more than 10k keys exist.

## Consequences
- Limits reset on every deploy or cold start. That's acceptable: the free instance sleeps
  after 15 minutes anyway.
- **Scaling out:** with more than one worker or instance, each keeps its own counts and
  the effective limit multiplies. Move to Redis (option 2) at that point.
- The chat endpoint in Milestone 3 can reuse `TokenBucket` with stricter guest limits.

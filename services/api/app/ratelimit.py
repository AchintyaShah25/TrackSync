"""In-memory token buckets for expensive endpoints (SPEC §7, decision 0023).

One uvicorn worker on Render, so process memory is the whole picture. Two buckets guard
`POST /strategy/simulate`: one per client and one global. The global bucket bounds CPU
even if a client rotates the X-Forwarded-For value it sends.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

from fastapi import HTTPException, Request

MAX_KEYS = 10_000


@dataclass
class TokenBucket:
    per_minute: float
    burst: float
    _state: dict[str, tuple[float, float]] = field(default_factory=dict)

    def take(self, key: str, now: float | None = None) -> float:
        """Spend one token. Returns 0 if allowed, else seconds until a token is available."""
        now = time.monotonic() if now is None else now
        rate = self.per_minute / 60.0
        tokens, last = self._state.get(key, (self.burst, now))
        tokens = min(self.burst, tokens + (now - last) * rate)
        if tokens >= 1.0:
            self._state[key] = (tokens - 1.0, now)
            if len(self._state) > MAX_KEYS:
                self._prune(now)
            return 0.0
        self._state[key] = (tokens, now)
        return (1.0 - tokens) / rate

    def _prune(self, now: float) -> None:
        full_after = self.burst / (self.per_minute / 60.0)
        for k, (_, last) in list(self._state.items()):
            if now - last > full_after:
                del self._state[k]


@dataclass
class SimulateLimiter:
    per_client: TokenBucket
    overall: TokenBucket

    @classmethod
    def create(cls, per_minute: int, global_per_minute: int) -> SimulateLimiter:
        return cls(
            per_client=TokenBucket(per_minute, burst=per_minute),
            overall=TokenBucket(global_per_minute, burst=global_per_minute),
        )


def client_key(request: Request) -> str:
    """Best-effort client id: first X-Forwarded-For hop (Render's proxy sets it)."""
    xff = request.headers.get("x-forwarded-for", "")
    first = xff.split(",")[0].strip()
    if first:
        return first
    return request.client.host if request.client else "unknown"


async def limit_simulate(request: Request) -> None:
    limiter: SimulateLimiter = request.app.state.simulate_limiter
    # Per-client first, so one noisy client does not drain the global budget.
    wait = limiter.per_client.take(client_key(request))
    if not wait:
        wait = limiter.overall.take("*")
    if wait:
        seconds = max(1, math.ceil(wait))
        raise HTTPException(
            429,
            f"too many simulations; try again in {seconds} s",
            headers={"Retry-After": str(seconds)},
        )

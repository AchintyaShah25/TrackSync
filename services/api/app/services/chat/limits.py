"""Chat limits for demo mode (decision 0032).

Per-minute bursts use in-memory token buckets (as simulate does, decision 0023). Per-day
caps live in Postgres (`usage_counters`) so a restart of the free API cannot reset them.
Guests are keyed by client IP and get stricter limits than signed-in users; a global daily
budget keeps the whole site under the LLM providers' free quotas.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from ...auth import User
from ...config import Settings
from ...ratelimit import TokenBucket, client_key

BUMP_SQL = text(
    """
    insert into usage_counters (key, day, count) values (:key, current_date, 1)
    on conflict (key, day) do update set count = usage_counters.count + 1
    returning count
    """
)


def _seconds_to_midnight_utc() -> int:
    now = datetime.now(UTC)
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(60, int((tomorrow - now).total_seconds()))


@dataclass
class ChatLimiter:
    guest_minute: TokenBucket
    user_minute: TokenBucket
    guest_per_day: int
    user_per_day: int
    global_per_day: int

    @classmethod
    def from_settings(cls, s: Settings) -> ChatLimiter:
        return cls(
            guest_minute=TokenBucket(s.chat_guest_per_minute, burst=s.chat_guest_per_minute),
            user_minute=TokenBucket(s.chat_user_per_minute, burst=s.chat_user_per_minute),
            guest_per_day=s.chat_guest_per_day,
            user_per_day=s.chat_user_per_day,
            global_per_day=s.chat_global_per_day,
        )

    async def check(self, engine: AsyncEngine, request: Request, user: User | None) -> None:
        key = f"chat:user:{user.id}" if user else f"chat:guest:{client_key(request)}"
        bucket = self.user_minute if user else self.guest_minute
        wait = bucket.take(key)
        if wait:
            secs = max(1, math.ceil(wait))
            raise HTTPException(
                429,
                f"too many questions; try again in {secs} s",
                headers={"Retry-After": str(secs)},
            )
        async with engine.begin() as conn:
            mine = (await conn.execute(BUMP_SQL, {"key": key})).scalar_one()
            everyone = (await conn.execute(BUMP_SQL, {"key": "chat:all"})).scalar_one()
        limit = self.user_per_day if user else self.guest_per_day
        if mine > limit or everyone > self.global_per_day:
            secs = _seconds_to_midnight_utc()
            reason = (
                "today's chat budget for the whole site is used up"
                if everyone > self.global_per_day
                else (
                    f"you have used today's {limit} questions"
                    + ("" if user else "; sign in for more")
                )
            )
            raise HTTPException(
                429, f"{reason}; it resets at midnight UTC", headers={"Retry-After": str(secs)}
            )

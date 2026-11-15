"""Sign-in token checks (decision 0030).

The browser signs in with Supabase Auth (magic link) and sends its access token as a Bearer
token. The API asks Supabase who the token belongs to (`GET /auth/v1/user`) and caches the
answer for a few minutes per token, so there is no extra dependency and no secret to hold.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import HTTPException, Request

from .llm.client import USER_AGENT

log = logging.getLogger(__name__)

CACHE_S = 300.0
MAX_CACHE = 5000

# (url, headers, timeout) -> (status, body)
GetTransport = Callable[[str, dict[str, str], float], tuple[int, bytes]]


def urllib_get(url: str, headers: dict[str, str], timeout: float) -> tuple[int, bytes]:
    # Supabase sits behind Cloudflare too; send the same generic agent as the LLM client.
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **headers}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as err:
        return err.code, err.read() or b""
    except (urllib.error.URLError, TimeoutError) as err:
        raise ConnectionError(str(err)) from err


@dataclass(frozen=True)
class User:
    id: str
    email: str | None = None


class AuthVerifier:
    def __init__(
        self,
        supabase_url: str,
        anon_key: str,
        transport: GetTransport = urllib_get,
        clock=time.monotonic,
    ):
        self.url = supabase_url.rstrip("/") + "/auth/v1/user" if supabase_url else ""
        self.anon_key = anon_key
        self._transport = transport
        self._clock = clock
        self._cache: dict[str, tuple[User | None, float]] = {}

    @property
    def configured(self) -> bool:
        return bool(self.url and self.anon_key)

    async def verify(self, token: str) -> User | None:
        """The user a token belongs to, or None if Supabase rejects it."""
        key = hashlib.sha256(token.encode()).hexdigest()
        now = self._clock()
        hit = self._cache.get(key)
        if hit and hit[1] > now:
            return hit[0]
        headers = {"apikey": self.anon_key, "Authorization": f"Bearer {token}"}
        try:
            status, body = await asyncio.to_thread(self._transport, self.url, headers, 5.0)
        except ConnectionError as err:
            log.warning("auth server unreachable: %s", err)
            raise HTTPException(503, "sign-in service unavailable; try again shortly") from err
        if status == 200:
            data = json.loads(body)
            user: User | None = User(id=str(data["id"]), email=data.get("email"))
        elif status in (401, 403):
            user = None
        else:
            log.warning("auth server returned %s", status)
            raise HTTPException(503, "sign-in service unavailable; try again shortly")
        if len(self._cache) >= MAX_CACHE:
            self._cache = {k: v for k, v in self._cache.items() if v[1] > now}
        self._cache[key] = (user, now + CACHE_S)
        return user


def _bearer(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    return token.strip() if scheme.lower() == "bearer" and token.strip() else None


async def optional_user(request: Request) -> User | None:
    """Signed-in user or None (guest). A token that is present but invalid is a 401, so the
    browser refreshes its session instead of silently getting guest limits."""
    token = _bearer(request)
    if token is None:
        return None
    verifier: AuthVerifier = request.app.state.auth
    if not verifier.configured:
        return None
    user = await verifier.verify(token)
    if user is None:
        raise HTTPException(401, "your session expired; sign in again")
    return user


async def current_user(request: Request) -> User:
    user = await optional_user(request)
    if user is None:
        raise HTTPException(401, "sign in to use this")
    return user

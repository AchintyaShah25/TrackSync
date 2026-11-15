"""Minimal OpenF1 client: rate limited, retried, and disk cached (docs/decisions/0004).

OpenF1 free tier: 3 req/s and 30 req/min, historical data (2023+) needs no key.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections import deque
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

log = logging.getLogger(__name__)

BASE_URL = "https://api.openf1.org/v1/"
USER_AGENT = "tracksync-etl (unofficial F1 analytics portfolio project)"

Rows = list[dict[str, Any]]


class OpenF1Error(RuntimeError):
    pass


class RateLimiter:
    """Sliding-window limiter: at most `per_minute` calls per 60 s and `per_second` per 1 s."""

    def __init__(
        self, per_minute: int, per_second: int = 3, clock=time.monotonic, sleep=time.sleep
    ):
        self.per_minute = per_minute
        self.per_second = per_second
        self._calls: deque[float] = deque()
        self._clock = clock
        self._sleep = sleep

    def wait(self) -> None:
        while True:
            now = self._clock()
            while self._calls and now - self._calls[0] >= 60:
                self._calls.popleft()
            last_second = sum(1 for t in self._calls if now - t < 1)
            if len(self._calls) < self.per_minute and last_second < self.per_second:
                self._calls.append(now)
                return
            if len(self._calls) >= self.per_minute:
                delay = 60 - (now - self._calls[0])
            else:
                delay = 1 - (now - self._calls[-self.per_second])
            self._sleep(max(delay, 0.05))


class OpenF1Client:
    def __init__(
        self,
        cache_dir: Path | None,
        per_minute: int = 28,
        session: requests.Session | None = None,
        max_retries: int = 8,
    ):
        self.cache_dir = cache_dir
        self.limiter = RateLimiter(per_minute)
        self.http = session or requests.Session()
        self.http.headers["User-Agent"] = USER_AGENT
        self.max_retries = max_retries
        self.requests_made = 0

    @staticmethod
    def build_url(endpoint: str, params: dict[str, Any]) -> str:
        """Build a query URL. Keys may carry OpenF1 operators, e.g. {"date>": "..."}."""
        parts = []
        for key, value in params.items():
            if key[-1] in "<>=":
                # operators go in the key: date>2024-... ; urlencode would escape them.
                parts.append(f"{key}{value}")
            else:
                parts.append(urlencode({key: value}))
        return BASE_URL + endpoint + ("?" + "&".join(parts) if parts else "")

    def _cache_path(self, url: str) -> Path | None:
        if self.cache_dir is None:
            return None
        digest = hashlib.sha256(url.encode()).hexdigest()[:24]
        return self.cache_dir / f"{digest}.json"

    def get(self, endpoint: str, *, cache: bool = True, **params: Any) -> Rows:
        """GET an endpoint. Returns [] when OpenF1 says 'No results found' (404)."""
        url = self.build_url(endpoint, params)
        path = self._cache_path(url) if cache else None
        if path is not None and path.exists():
            return json.loads(path.read_text())

        delay = 2.0
        for attempt in range(1, self.max_retries + 1):
            self.limiter.wait()
            self.requests_made += 1
            try:
                resp = self.http.get(url, timeout=60)
            except requests.RequestException as exc:
                log.warning("OpenF1 request failed (%s), attempt %d: %s", url, attempt, exc)
                resp = None
            if resp is not None:
                if resp.status_code == 404:
                    rows: Rows = []
                    break
                if resp.ok:
                    rows = resp.json()
                    break
                if resp.status_code not in (429, 500, 502, 503, 504):
                    raise OpenF1Error(f"{resp.status_code} for {url}: {resp.text[:200]}")
                wait = delay
                if resp.status_code == 429:
                    # The per-minute window may have been spent by another process (or a
                    # previous run), which our limiter cannot see: honor Retry-After, else
                    # wait out a full window.
                    retry_after = resp.headers.get("Retry-After") if resp.headers else None
                    wait = float(retry_after) if retry_after and retry_after.isdigit() else 61
                log.warning("OpenF1 %s for %s, retrying in %.0fs", resp.status_code, url, wait)
                time.sleep(wait)
            else:
                time.sleep(delay)
            delay = min(delay * 2, 60)
        else:
            raise OpenF1Error(f"giving up after {self.max_retries} attempts: {url}")

        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(rows))
        return rows

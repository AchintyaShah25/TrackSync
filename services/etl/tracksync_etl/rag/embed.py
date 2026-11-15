"""Document embeddings with Gemini `gemini-embedding-001` (768 dims, L2-normalized),
batched 100 at a time. Without GEMINI_API_KEY nothing is embedded and search uses
Postgres full-text only (decision 0027)."""

from __future__ import annotations

import logging
import math
import time

import requests

log = logging.getLogger(__name__)

MODEL = "gemini-embedding-001"
DIM = 768
BATCH = 100
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:batchEmbedContents"


def _normalize(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _daily_quota(resp) -> bool:
    """True when a 429 is the per-day quota (no point retrying today), not per-minute."""
    try:
        details = resp.json().get("error", {}).get("details", [])
    except (ValueError, AttributeError):
        return False
    return any(
        "PerDay" in v.get("quotaId", "")
        for d in details
        if isinstance(d, dict)
        for v in d.get("violations", [])
    )


class Embedder:
    def __init__(self, api_key: str, session: requests.Session | None = None, pause_s: float = 1.0):
        self.api_key = api_key
        self.session = session or requests.Session()
        self.pause_s = pause_s
        self.requests_made = 0
        # Set when Google reports the per-day free quota (1000 texts) is used up; later
        # calls return None at once instead of retrying every document (decision 0034).
        self.exhausted = False

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def embed(self, texts: list[str], titles: list[str]) -> list[list[float]] | None:
        """Embeddings for `texts` (same order), or None when disabled or failing."""
        if not self.enabled or self.exhausted or not texts:
            return None
        out: list[list[float]] = []
        for i in range(0, len(texts), BATCH):
            body = {
                "requests": [
                    {
                        "model": f"models/{MODEL}",
                        "content": {"parts": [{"text": t}]},
                        "taskType": "RETRIEVAL_DOCUMENT",
                        "title": title[:200],
                        "outputDimensionality": DIM,
                    }
                    for t, title in zip(texts[i : i + BATCH], titles[i : i + BATCH], strict=True)
                ]
            }
            vectors = self._post(body)
            if vectors is None:
                return None
            out += [_normalize(v) for v in vectors]
        return out

    def _post(self, body: dict) -> list[list[float]] | None:
        for attempt in range(4):
            self.requests_made += 1
            resp = self.session.post(
                URL, json=body, headers={"x-goog-api-key": self.api_key}, timeout=60
            )
            if resp.status_code == 429:
                if _daily_quota(resp):
                    self.exhausted = True
                    log.warning("daily embedding quota used up; the rest stays text-only")
                    return None
                wait = float(resp.headers.get("retry-after", 20 * (attempt + 1)))
                log.info("embedding rate limited; waiting %.0fs", wait)
                time.sleep(min(wait, 90))
                continue
            if resp.status_code != 200:
                log.warning("embedding failed: %s %s", resp.status_code, resp.text[:200])
                return None
            time.sleep(self.pause_s)  # stay well under the free per-minute quota
            return [e["values"] for e in resp.json()["embeddings"]]
        log.warning("embedding gave up after repeated rate limits")
        return None

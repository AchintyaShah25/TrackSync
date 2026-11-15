"""Query embeddings for knowledge search (decision 0027).

Gemini `gemini-embedding-001` truncated to 768 dimensions and L2-normalized (truncated
Matryoshka embeddings must be renormalized). The ETL embeds documents the same way with
taskType RETRIEVAL_DOCUMENT. Any failure returns None, and search falls back to full-text.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math

from .client import Transport, Unavailable, urllib_transport

log = logging.getLogger(__name__)

EMBED_MODEL = "gemini-embedding-001"
EMBED_DIM = 768
EMBED_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{EMBED_MODEL}:embedContent"


def normalize(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


async def embed_query(
    text: str, api_key: str, transport: Transport = urllib_transport, timeout_s: float = 8.0
) -> list[float] | None:
    if not api_key or not text.strip():
        return None
    body = {
        "model": f"models/{EMBED_MODEL}",
        "content": {"parts": [{"text": text[:2000]}]},
        "taskType": "RETRIEVAL_QUERY",
        "outputDimensionality": EMBED_DIM,
    }
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
    try:
        status, _, raw = await asyncio.to_thread(
            transport, EMBED_URL, headers, json.dumps(body).encode(), timeout_s
        )
        if status != 200:
            log.warning("embedding returned %s; using full-text search only", status)
            return None
        values = json.loads(raw)["embedding"]["values"]
    except (Unavailable, ValueError, KeyError, TypeError) as err:
        log.warning("embedding failed (%s); using full-text search only", err)
        return None
    if len(values) != EMBED_DIM:
        return None
    return normalize([float(x) for x in values])

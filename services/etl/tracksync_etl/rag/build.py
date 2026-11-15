"""Assemble the knowledge base: which documents to (re)build on a run."""

from __future__ import annotations

import logging
from collections import Counter
from pathlib import Path

from sqlalchemy import Engine, text

from .embed import Embedder
from .load import store_documents
from .sources import Document, Fetcher, fia_documents, wikipedia_document
from .summaries import race_summaries

log = logging.getLogger(__name__)

EVENT_NAMES_SQL = text(
    """
    select e.id, e.season, e.name from events e
    where exists (select 1 from results r where r.event_id = e.id and r.session = 'R')
      and (cast(:ids as integer[]) is null or e.id = any(cast(:ids as integer[])))
    order by e.id
    """
)


def refresh_knowledge(
    engine: Engine,
    cache_dir: Path,
    embedder: Embedder,
    *,
    event_ids: list[int] | None = None,
    full: bool = False,
    seasons: list[int] | None = None,
    current_season: int | None = None,
    fetcher: Fetcher | None = None,
) -> Counter:
    """`full`: FIA regulations, season articles and every race. Otherwise only the races
    in `event_ids` (summary + Wikipedia article), as the weekly run does."""
    fetcher = fetcher or Fetcher(cache_dir)
    docs: list[Document] = []
    ids = None if full else event_ids
    with engine.connect() as conn:
        docs += race_summaries(conn, ids)
        events = conn.execute(EVENT_NAMES_SQL, {"ids": ids}).all()
    for ev in events:
        doc = _safe(lambda ev=ev: wikipedia_document(
            fetcher, f"{ev.season} {ev.name}", season=ev.season, event_id=ev.id
        ))  # fmt: skip
        if doc:
            docs.append(doc)
    if full:
        for season in seasons or []:
            doc = _safe(lambda s=season: wikipedia_document(
                fetcher, f"{s} Formula One World Championship", season=s
            ))  # fmt: skip
            if doc:
                docs.append(doc)
        if current_season:
            docs += _safe(lambda: fia_documents(fetcher, current_season)) or []
    counts = store_documents(engine, docs, embedder)
    counts["rag_embed_requests"] = embedder.requests_made
    log.info("knowledge base: %s", dict(counts))
    return counts


def _safe(fn):
    """One unreachable source must not abort the run."""
    try:
        return fn()
    except Exception:
        log.exception("knowledge source failed")
        return None

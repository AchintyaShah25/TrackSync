"""Write documents and chunks. A document whose content hash is unchanged (and whose chunks
are already embedded, when embedding is enabled) is skipped, so weekly runs are cheap."""

from __future__ import annotations

import logging
from collections import Counter

from sqlalchemy import Engine, text

from .chunk import chunk_sections
from .embed import Embedder
from .sources import Document

log = logging.getLogger(__name__)

EXISTING_SQL = text(
    """
    select d.id, d.content_hash,
           bool_and(c.embedding is not null) as embedded, count(c.id) as chunks
    from rag_documents d left join rag_chunks c on c.document_id = d.id
    where d.source_key = :key group by d.id
    """
)
UPSERT_DOC_SQL = text(
    """
    insert into rag_documents (source, source_key, title, url, license, season, event_id,
                               content_hash, updated_at)
    values (:source, :source_key, :title, :url, :license, :season, :event_id, :hash, now())
    on conflict (source_key) do update set
      title = excluded.title, url = excluded.url, license = excluded.license,
      season = excluded.season, event_id = excluded.event_id,
      content_hash = excluded.content_hash, updated_at = now()
    returning id
    """
)
INSERT_CHUNK_SQL = text(
    """
    insert into rag_chunks (document_id, ord, section, heading, content, embedding)
    values (:doc, :ord, :section, :heading, :content, cast(:embedding as extensions.vector))
    """
)


def _heading(doc: Document, section: str) -> str:
    """Search heading (weighted highest). Regulation chunks leave out the year and issue:
    stamped on 700 chunks they would make "2026" look like a common word."""
    if doc.source == "fia":
        return f"FIA F1 regulations {section}"[:300]
    return f"{doc.title} {section}"[:300]


def store_documents(engine: Engine, docs: list[Document], embedder: Embedder) -> Counter:
    counts: Counter = Counter()
    for doc in docs:
        chunks = chunk_sections(doc.sections)
        if not chunks:
            counts["rag_empty"] += 1
            continue
        with engine.connect() as conn:
            existing = conn.execute(EXISTING_SQL, {"key": doc.source_key}).first()
        up_to_date = (
            existing is not None
            and existing.content_hash == doc.content_hash
            and existing.chunks > 0
            and (existing.embedded or not embedder.enabled)
        )
        if up_to_date:
            counts["rag_unchanged"] += 1
            continue
        if (
            getattr(embedder, "exhausted", False)
            and existing is not None
            and (existing.content_hash in (doc.content_hash, "pending") and existing.chunks > 0)
        ):
            # Quota gone for today: rewriting an unembedded document without vectors would
            # gain nothing. The next run embeds it.
            counts["rag_deferred"] += 1
            continue
        vectors = embedder.embed(
            [c.content for c in chunks], [f"{doc.title} — {c.section}" for c in chunks]
        )
        with engine.begin() as conn:
            doc_id = conn.execute(
                UPSERT_DOC_SQL,
                {
                    "source": doc.source,
                    "source_key": doc.source_key,
                    "title": doc.title,
                    "url": doc.url,
                    "license": doc.license,
                    "season": doc.season,
                    "event_id": doc.event_id,
                    # Without embeddings, store a marker hash so a later run with a key
                    # re-embeds this document.
                    "hash": doc.content_hash if vectors or not embedder.enabled else "pending",
                },
            ).scalar_one()
            conn.execute(text("delete from rag_chunks where document_id = :d"), {"d": doc_id})
            conn.execute(
                INSERT_CHUNK_SQL,
                [
                    {
                        "doc": doc_id,
                        "ord": i,
                        "section": c.section[:200],
                        "heading": _heading(doc, c.section),
                        "content": c.content,
                        "embedding": str(vectors[i]) if vectors else None,
                    }
                    for i, c in enumerate(chunks)
                ],
            )
        counts["rag_documents"] += 1
        counts["rag_chunks"] += len(chunks)
        counts["rag_embedded"] += len(chunks) if vectors else 0
    return counts

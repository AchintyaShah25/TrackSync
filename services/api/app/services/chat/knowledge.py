"""`search_knowledge`: hybrid retrieval over the knowledge base (decision 0027).

Two ranked lists merged with reciprocal rank fusion (RRF): pgvector cosine similarity on
Gemini embeddings and Postgres full-text search. When the query cannot be embedded (no key,
quota spent, provider down) or chunks have no vectors yet, full-text alone still answers.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

RRF_K = 60
CANDIDATES = 30
SOURCES = ("fia", "wikipedia", "summary")
# Words in more than this share of chunks carry little signal. Postgres ranking has no IDF,
# so such words ("grand", "prix", "race") would otherwise swamp the distinctive ones.
COMMON_SHARE = 0.25
KEEP_RAREST = 3
DF_TTL_S = 3600.0
_df_cache: tuple[float, int, dict[str, int]] | None = None


@dataclass
class Hit:
    chunk_id: int
    title: str
    section: str | None
    url: str | None
    license: str
    source: str
    content: str
    score: float


async def _document_frequencies(conn: AsyncConnection) -> tuple[int, dict[str, int]]:
    """Chunk count and per-lexeme chunk frequency, cached for an hour per process."""
    global _df_cache
    now = time.monotonic()
    if _df_cache and _df_cache[0] > now:
        return _df_cache[1], _df_cache[2]
    total = await conn.scalar(text("select count(*) from rag_chunks")) or 0
    rows = (
        await conn.execute(text("select word, ndoc from ts_stat('select tsv from rag_chunks')"))
    ).all()
    _df_cache = (now + DF_TTL_S, total, {w: n for w, n in rows})
    return total, _df_cache[2]


def build_tsquery(lexemes: list[str], total: int, df: dict[str, int]) -> str | None:
    """OR of the question's distinctive lexemes, quoted for to_tsquery('simple', ...).

    Lexemes found in more than COMMON_SHARE of chunks are dropped; if that leaves nothing,
    the KEEP_RAREST rarest are used. Unknown words are dropped (they match nothing).
    """
    known = [w for w in dict.fromkeys(lexemes) if w in df]
    if not known:
        return None
    keep = [w for w in known if total and df[w] / total <= COMMON_SHARE]
    if not keep:
        keep = sorted(known, key=lambda w: df[w])[:KEEP_RAREST]
    return " | ".join("'" + w.replace("'", "''") + "'" for w in keep[:24])


FILTERS = """
    (cast(:source as text) is null or d.source = :source)
    and (cast(:season as integer) is null or d.season = :season or d.season is null)
"""


async def search(
    conn: AsyncConnection,
    question: str,
    embedding: list[float] | None,
    *,
    k: int = 5,
    source: str | None = None,
    season: int | None = None,
) -> list[Hit]:
    k = min(max(k, 1), 6)
    source = source if source in SOURCES else None
    lexemes = (
        await conn.scalar(
            text("select tsvector_to_array(to_tsvector('english', :q))"), {"q": question[:500]}
        )
    ) or []
    total, df = await _document_frequencies(conn)
    tsq = build_tsquery(list(lexemes), total, df)
    if tsq is None and embedding is None:
        return []
    parts, params = [], {"source": source, "season": season, "n": CANDIDATES}
    if embedding is not None:
        params["emb"] = str(embedding)
        parts.append(
            f"""
            select c.id, row_number() over (
                     order by c.embedding <=> cast(:emb as extensions.vector)) as r
            from rag_chunks c join rag_documents d on d.id = c.document_id
            where c.embedding is not null and {FILTERS}
            order by c.embedding <=> cast(:emb as extensions.vector) limit :n
            """
        )
    if tsq is not None:
        params["tsq"] = tsq
        parts.append(
            f"""
            select c.id, row_number() over (
                     order by ts_rank_cd(c.tsv, to_tsquery('simple', :tsq)) desc) as r
            from rag_chunks c join rag_documents d on d.id = c.document_id
            where c.tsv @@ to_tsquery('simple', :tsq) and {FILTERS}
            order by ts_rank_cd(c.tsv, to_tsquery('simple', :tsq)) desc limit :n
            """
        )
    ranked = " union all ".join(f"({p})" for p in parts)
    rows = (
        await conn.execute(
            text(
                f"""
                with ranked as ({ranked}),
                fused as (select id, sum(1.0 / ({RRF_K} + r)) as score from ranked group by id)
                select c.id, d.title, c.section, d.url, d.license, d.source, c.content, f.score
                from fused f join rag_chunks c on c.id = f.id
                join rag_documents d on d.id = c.document_id
                order by f.score desc limit :k
                """
            ),
            {**params, "k": k},
        )
    ).all()
    return [Hit(*r) for r in rows]

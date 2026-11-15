# 0027: Hybrid retrieval (pgvector + full-text) with Gemini embeddings

- **Status:** Accepted (closes the SPEC §9 open decision on embeddings; daily quota handling amended by 0034)
- **Date:** 2026-11-16
- **Milestone:** 3

## Context
`search_knowledge` needs good recall over FIA regulations and Wikipedia articles. Render's
free API has about 512 MB of RAM, which rules out a local embedding model in the API. The
embedding provider can also be rate-limited or down.

## Options considered
1. **A local embedding model (fastembed or ONNX) in the API:** about 150 MB+ of RAM and
   a slow cold start on the free instance.
2. **A free embedding API only:** search fails whenever the API is unavailable.
3. **A free embedding API plus Postgres full-text search, merged by reciprocal rank
   fusion (RRF):** search still works on full-text alone when embeddings are unavailable.

## Decision
Option 3.
- **Embeddings:** Gemini `gemini-embedding-001` truncated to 768 dimensions and
  L2-normalized. Documents use task type RETRIEVAL_DOCUMENT and questions
  RETRIEVAL_QUERY.
- **Storage:** a pgvector HNSW (cosine) index.
- **Full-text:** a `tsvector` that weights a heading (document title + section) as A and
  the body as D.
- **Postgres ranking has no IDF**, so the query keeps only words found in at most 25% of
  chunks, from `ts_stat` document frequencies cached for an hour; failing that, the
  three rarest. That replaced a hand-made stopword list, which removed title words such
  as "championship".
- **Fusion:** RRF with k = 60 over the top 30 of each list.

## Consequences
- **Full-text-only retrieval:** 84% hit@5 on the golden set (rules 76%, history 93%),
  above the 70% target (evals/chat/results.md). Hybrid scores are recorded once
  embeddings run.
- **Size:** about 2.9k chunks, roughly 6 MB of text plus about 9 MB of vectors.
- **Rebuild:** the ETL rebuilds documents whose content hash changed. Documents stored
  before a key existed are marked so the next run embeds them.

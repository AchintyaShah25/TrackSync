# 0034: Living with Gemini's 1000-per-day embedding quota

- **Status:** Accepted (amends the embedding plan in 0027)
- **Date:** 2026-11-15
- **Milestone:** 3

## Context
The first full `make etl ARGS=--rag` with a real key stopped after 982 of 2,543 chunks.
The 429 response named the quota
`EmbedContentRequestsPerDayPerUserPerProjectPerModel-FreeTier`, limit 1000. Each text in
a `batchEmbedContents` call counts as one request, so batching does not help. Decision
0027 assumed only a per-minute limit. The embedder also treated every 429 as a per-minute
limit: it retried each remaining document for about 3 minutes and then marked it
`pending`.

The same key embeds chat questions at query time, so chat and the ETL share the 1000.

## Options considered
1. **Paid Gemini tier:** removes the limit, but adds a paid service; ruled out by the
   free-tier rule.
2. **A different free embedding provider:** another account and key, and a
   re-embedding of everything already stored.
3. **Fill the knowledge base over several days:** stop as soon as the daily quota is
   gone and finish on later runs. The `pending` marker and content-hash skip (0027)
   already support this.

## Decision
Option 3.
- **Stop at the daily quota.** The embedder now recognises the per-day quota error. It
  stops making requests for the rest of the run, and the loader leaves unembedded
  documents untouched instead of rewriting them without vectors.
- **Finish the first build over about two more daily runs** (about 1,560 chunks left).
- **Weekly upkeep fits easily:** new race summaries and articles are a few dozen chunks a
  week.

## Consequences
- **Hybrid search is partial until the backfill finishes.** Chunks without vectors are
  still found by full-text search, so answers are not blocked; vector recall improves as
  the backfill completes.
- **Chat embeds every question.** With a site-wide chat cap of 800 a day (0032), a busy
  day plus an ETL backfill could exhaust the quota. When it runs out, `embed_query`
  fails and search falls back to full-text only (0027), so chat keeps working at
  slightly lower recall.
- **Revisit** if traffic grows: cache question embeddings, or move to a paid tier with
  the owner's approval.

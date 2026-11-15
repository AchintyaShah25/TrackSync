# 0028: Knowledge sources, licensing and attribution

- **Status:** Accepted
- **Date:** 2026-11-16
- **Milestone:** 3

## Context
CLAUDE.md limits retrieval sources to FIA regulation documents, Wikipedia (CC BY-SA,
attributed in the UI) and summaries generated from our own data. News sites must not be
scraped.

## Decision
- **FIA:** the current season's newest issues of F1 Regulations Section A (General
  Provisions, which includes the points system) and Section B (Sporting). They come from
  the FIA's public regulations page, are parsed with pypdf, and are split by article
  ("A2.2 Championship points system"). Running headers and the table of contents are
  removed. Licence line: "© FIA. Excerpt quoted for reference; the official document
  prevails."
- **Wikipedia:** season articles (2023+) and every Grand Prix article we have results for,
  taken from the MediaWiki plain-text extracts API. Classification and standings tables
  are skipped, since stats must come from `query_stats`. Licence "CC BY-SA 4.0 (Wikipedia
  contributors)", stored with the title and canonical URL; the chat UI shows these with
  every citation.
- **Race summaries:** a fixed template, no LLM, filled from our tables: podium and gap,
  pole, fastest lap, SC/VSC periods, the winner's stops and the DNFs. Licence line names
  OpenF1 (CC BY-NC-SA 4.0) and Jolpica-F1.
- **Fetching:**
  - Every fetch is cached on disk.
  - Uncached requests are spaced 0.5 s apart, with retries on 429/503 (Wikipedia
    throttled the first unpaced build).
  - A generic User-Agent is sent; no personal or project details go to third parties.

## Consequences
- The weekly ETL refreshes summaries and articles for newly loaded races. `--rag`
  rebuilds everything, including new FIA issues.
- OpenF1 is non-commercial (CC BY-NC-SA), which already matches the footer and SPEC.

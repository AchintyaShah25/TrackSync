# Decision records

One file per decision, numbered in order. Use `0000-template.md`. To reverse a decision,
write a new record that supersedes the old one.

| # | Title | Status | Date |
|---|---|---|---|
| 0001 | Decouple FastF1 ETL from the API | Accepted | 2026-11-14 |
| 0002 | Trim v1 scope to three hero features | Accepted | 2026-11-14 |
| 0003 | Isolated, project-local toolchain | Accepted | 2026-11-14 |
| 0004 | Session data from OpenF1; FastF1 kept only for Jolpica and circuit info | Accepted | 2026-11-14 |
| 0005 | Natural keys and idempotent loads | Accepted | 2026-11-14 |
| 0006 | Fastest-lap traces as 300-point columnar jsonb | Accepted | 2026-11-14 |
| 0007 | Circuit outline from the pole lap, in a shared normalized frame | Accepted | 2026-11-14 |
| 0008 | Standings stored as a Jolpica snapshot | Accepted | 2026-11-14 |
| 0009 | Keep the repo outside iCloud-synced folders | Accepted (location superseded by 0015) | 2026-11-14 |
| 0010 | Static showcase pages with build-time generation and daily ISR | Accepted | 2026-11-14 |
| 0011 | Track map as a hand-rolled SVG component | Accepted | 2026-11-14 |
| 0012 | Local dev stack: Supabase CLI containers + compose for app services | Accepted (`make up` amended by 0017) | 2026-11-14 |
| 0013 | Tests use throwaway databases on the local Supabase Postgres | Accepted | 2026-11-14 |
| 0014 | Project name TrackSync; internal identifiers keep `pitwall` for now | Accepted (internals superseded by 0016) | 2026-11-14 |
| 0015 | Repo lives at ~/Desktop/TrackSync.nosync | Accepted | 2026-11-14 |
| 0016 | Internal identifiers renamed from `pitwall` to `tracksync` | Accepted | 2026-11-14 |
| 0017 | `make up` starts only Postgres until auth lands | Superseded in part by 0031 | 2026-11-15 |
| 0018 | Production hosting setup and connection routing | Accepted | 2026-11-15 |
| 0019 | Mask database connection details in public workflow logs | Accepted | 2026-11-15 |
| 0020 | Race model form and fitting (fixed effects + ridge shrinkage to global) | Accepted | 2026-11-15 |
| 0021 | Monte Carlo race simulator design | Accepted | 2026-11-15 |
| 0022 | Model params keyed by (circuit, model_version) | Accepted | 2026-11-16 |
| 0023 | In-memory rate limiter for simulate, no new dependency | Accepted | 2026-11-16 |
| 0024 | Forecast page: static POST example, strategy colours, URL state | Accepted | 2026-11-16 |
| 0025 | Merge OpenF1 stints that continue the same tyre set | Accepted | 2026-11-16 |
| 0026 | LLM providers, fallback chain, and no SDK | Accepted | 2026-11-16 |
| 0027 | Hybrid retrieval (pgvector + full-text) with Gemini embeddings | Accepted | 2026-11-16 |
| 0028 | Knowledge sources, licensing and attribution | Accepted | 2026-11-16 |
| 0029 | Agent tools: allow-listed stats queries and grounded charts | Accepted | 2026-11-16 |
| 0030 | Magic-link sign-in; API checks tokens with Supabase; RLS inside the API | Accepted | 2026-11-16 |
| 0031 | `make up` runs the Supabase stack minus unused services | Accepted (supersedes part of 0017) | 2026-11-16 |
| 0032 | Chat history in the browser; durable daily limits; guest vs user limits | Accepted | 2026-11-16 |
| 0033 | End-to-end tests mock the chat API in the browser | Accepted | 2026-11-16 |
| 0034 | Living with Gemini's 1000-per-day embedding quota | Accepted | 2026-11-15 |
| 0035 | Groq model `openai/gpt-oss-120b`; Gemini is only a thin fallback | Accepted (supersedes the default model in 0026) | 2026-11-15 |

# 0026: LLM providers, fallback chain, and no SDK

- **Status:** Accepted (default Groq model superseded by 0035)
- **Date:** 2026-11-16
- **Milestone:** 3

## Context
The chat agent needs a model that supports tool calling, on free tiers only (CLAUDE.md
rule 3). Checked 2026-11-16:
- **Groq free:** about 30 requests/min with low token-per-minute caps.
- **Gemini free:** Flash only, with limits cut through 2025–26.

Either one alone runs out quickly. The API service has no HTTP client dependency, and the
owner approved none for the API.

## Options considered
1. **One provider through its SDK:** simplest, but a busy minute means no answers, and it
   adds a dependency.
2. **LiteLLM or another router library:** heavy, and many dependencies on a small instance.
3. **One OpenAI-compatible client** (both providers expose `/chat/completions` with
   tools) over the standard library, with an ordered fallback chain.

## Decision
Option 3 (`services/api/app/llm/`):
- **Client:** `urllib` in a worker thread, with an injectable transport for tests.
- **Chain:** `LLM_CHAIN=groq,gemini`. Default models `llama-3.3-70b-versatile` (Groq) and
  `gemini-2.5-flash`; both configurable.
- **Failover:** a 429 benches a provider until Retry-After, and a 5xx or bad key benches
  it for 30 s. A malformed reply falls through for that request only. When all providers
  are down, chat returns 503 with Retry-After.
- **Missing keys:** a provider without a key is skipped. With none, chat answers 503
  "not configured" and the rest of the site works.

## Consequences
- The agent loop is capped at 4 tool rounds plus a forced final answer, to fit free quotas.
- Swapping or adding a provider is configuration only, as long as it is OpenAI-compatible.
- The chat page states that free-tier providers may use prompts to improve their models.

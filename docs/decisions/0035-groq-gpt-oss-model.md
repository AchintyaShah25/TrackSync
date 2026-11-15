# 0035: Groq model `openai/gpt-oss-120b`; Gemini is only a thin fallback

- **Status:** Accepted (supersedes the default-model choice in 0026)
- **Date:** 2026-11-15
- **Milestone:** 3

## Context
The first agent eval with real keys (2026-11-15) answered only 10 of 52 questions:
- **Groq** returned 404 `model_not_found` for `llama-3.3-70b-versatile`, the default in
  0026. Groq has retired it; the key now lists `openai/gpt-oss-120b`,
  `openai/gpt-oss-20b` and `qwen/qwen3.8-27b` among the chat models.
- **Gemini** answered 10 questions, then hit
  `GenerateRequestsPerDayPerProjectPerModel-FreeTier` = **20 requests/day** for
  `gemini-2.5-flash`. An agent turn takes 2–4 requests, so that is 5–10 chats a day.

`openai/gpt-oss-120b` on the free tier: 1000 requests a day and 8000 tokens a minute
(from the response headers). A test call with a tool schema returned a proper tool call.

## Options considered
1. **`openai/gpt-oss-120b`:** the largest model on the key; supports tool calling. It
   also spends tokens on reasoning (about 130 per short call), which counts toward the
   8000 tokens a minute.
2. **`openai/gpt-oss-20b`:** faster and cheaper in tokens, but weaker at picking tools
   and parameters.
3. **`qwen/qwen3.8-27b`:** untested here for tool calling.

## Decision
Option 1 as the default (`GROQ_MODEL`, still configurable). The chain stays
`groq,gemini`, but Gemini is a last resort, good for a handful of chats a day.

## Consequences
- **Groq carries the chat.** 1000 requests a day covers the site-wide cap of 800 chats
  (0032) only if most chats take one or two rounds. The per-minute token cap means about
  1–2 agent turns a minute site-wide; busy minutes return the friendly 503 with
  Retry-After.
- **Model names drift.** Free providers retire models without notice. A 404 benches the
  provider for 30 s like a bad key (0026), so the site degrades instead of failing; the
  manual eval workflow (`eval.yml`) is the place where a retired model shows up.
- **Revisit** if Groq's free limits change, or if a larger free model with tool calling
  appears.

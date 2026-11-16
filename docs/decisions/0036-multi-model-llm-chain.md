# 0036: Several models per provider in the LLM chain; site-wide chat cap sized to them

- **Status:** Accepted (extends 0026 and 0035; changes the site-wide cap in 0032)
- **Date:** 2026-11-15
- **Milestone:** 3

## Context
After the evals, a follow-up chat question failed with "assistant busy". Groq's 429 body
said: tokens per day (TPD) for `openai/gpt-oss-120b`, limit 200,000, used 199,038.
An agent turn costs about 2–5k tokens, so one free Groq model serves roughly 40–80 chats
a day. Gemini Flash adds 20 requests a day (0035). The site-wide cap of 800 chats a day
(0032) was far above what the providers can serve. Busy days would have produced
repeated 503s instead of the clearer daily-limit message.

Groq's free quotas are per model. `openai/gpt-oss-20b` and `qwen/qwen3.8-27b` each report
1000 requests a day and 8000 tokens a minute, and both returned correct tool calls in a
test. Qwen's answers have no inline `<think>` text.

## Options considered
1. **One model per provider (as before):** about 40–80 chats a day.
2. **Several Groq models in the chain:** about 3× the daily capacity. A smaller model
   answers when the larger one is out of quota, so quality drops a little on busy days.
3. **Groq Dev tier:** a paid service; ruled out by the free-tier rule.

## Decision
Option 2.
- **Chain entries:** `LLM_CHAIN` entries are `provider` (its default model) or
  `provider:model`.
- **Cooldowns are per model,** so one model's daily cap doesn't bench the others.
- **Default chain:** `groq:openai/gpt-oss-120b, groq:qwen/qwen3.8-27b,
  groq:openai/gpt-oss-20b, gemini`.
- **Site-wide cap:** `CHAT_GLOBAL_PER_DAY` drops from 800 to 150: about 600k Groq tokens
  a day at about 4k per chat.
- **Logging:** the client logs the 429 body, so the logs say which limit was hit.

## Consequences
- **Busy days degrade gracefully.** The first questions of a busy day get the 120b
  model; later ones get Qwen or 20b. The response's `model` field says which.
- **The evals measured gpt-oss-120b only** (0035). Smaller models may score lower on
  answer correctness; re-run `make eval` with `LLM_CHAIN` set to a single model to
  measure each.
- **Revisit** if Groq changes its free models or quotas. Retired model names show up as
  404s, which bench that model for 30 s (0026).

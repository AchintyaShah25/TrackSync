# 0032: Chat history in the browser; durable daily limits; guest vs user limits

- **Status:** Accepted (site-wide cap changed by 0036)
- **Date:** 2026-11-16
- **Milestone:** 3

## Context
- **History:** the owner chose to keep chat history only in the browser, so the server
  stores no chat text.
- **Demo mode:** guests can use chat, with stricter limits (SPEC §7).
- **Restarts:** the free API restarts after 15 minutes idle, and in-memory counters
  would reset each time.

## Decision
- **History:**
  - Conversations live in `localStorage` (the last 40 messages, with a "Clear chat"
    button).
  - Only the last 12 messages, each capped at 2,000 characters, are sent with a question.
- **Limits:**
  - Per minute, in memory (TokenBucket, decision 0023): guests 5, users 10.
  - Per day, in Postgres (`usage_counters`, upserted atomically): guests 30 by IP, users
    100, and a site-wide 800 kept under the providers' free daily quotas.
  - A 429 carries Retry-After (seconds to midnight UTC for daily limits) and a "sign in
    for more" hint for guests.
- **Privacy notice:** the chat page states that questions go to free AI providers that
  may use them, and asks people not to share personal details.

## Consequences
- **Privacy:** no chat text sits in our database; `usage_counters` holds only
  `chat:guest:<ip>` and `chat:user:<uuid>` keys with counts. Old rows can be pruned.
  They're tiny, but a cleanup job could come in Milestone 4.
- **Limitation:** the guest per-IP limit can be dodged by changing IP. The site-wide daily
  cap is the hard bound.

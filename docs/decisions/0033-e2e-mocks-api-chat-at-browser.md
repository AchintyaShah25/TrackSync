# 0033: End-to-end tests mock the chat API in the browser

- **Status:** Accepted
- **Date:** 2026-11-16
- **Milestone:** 3

## Context
Playwright runs against a fixture build with the API on a dead port (decision 0010), so
static pages are tested with the API asleep. Chat is dynamic and calls a paid-quota LLM,
so it cannot be pre-recorded the way showcase pages are.

## Decision
- **Chat mocks:** e2e tests intercept only the API's `/chat` (matched by the API port and
  path, not the site's `/chat` page) with `page.route` and return a fixed response. That
  checks the UI contract: markdown, [n] citation links, the licence line per source, the
  inline chart, the tool trace, and the 429 message.
- **Sign-in UI:** the e2e build sets a placeholder Supabase URL and key so the guest
  sign-in UI renders; tests never call Supabase.
- **What isn't covered here:** the agent's real behaviour is covered by the API tests with
  a scripted LLM (test_chat.py) and by the golden-set eval.

## Consequences
- The mocked response must follow `ChatResponse` (services/api/app/schemas/chat.py). A
  schema change means updating the mock alongside `lib/api/types.ts`.

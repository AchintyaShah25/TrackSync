# 0002: Trim v1 scope to three hero features

- **Status:** Accepted
- **Date:** 2026-11-14
- **Milestone:** 1

## Context
The original plan had eight phases, including a browser racing game, race-week
time-trial leaderboards with anti-cheat, and race replay. Built by one person alongside
coursework, that scope risked a half-finished app. Portfolio reviewers spend under a
minute on a project, so finish and polish matter more than feature count.

## Options considered
1. **Build everything in v1**: most features, highest risk of nothing feeling finished.
2. **Three hero features + polish, rest in a v2 backlog**: each feature proves a
   different skill (data engineering, applied ML, LLM engineering) and can be polished.

## Decision
Option 2. v1 is race analytics, the strategy forecaster, and the chat agent, with auth,
light personalization, demo mode, and static showcase pages. The game, time trials,
replay, and pre-2023 seasons move to the v2 backlog in `docs/SPEC.md`.

## Consequences
Less breadth, but a finished, fast, well-documented app. The X/Y circuit outlines built
in Milestone 1 keep the game cheap to add later.

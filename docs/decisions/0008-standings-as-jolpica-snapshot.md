# 0008: Standings stored as a Jolpica snapshot

- **Status:** Accepted
- **Date:** 2026-11-14
- **Milestone:** 1

## Context
`GET /standings/{year}` needs driver and constructor standings. They could be computed
by summing `results.points`, but edge cases make that error-prone: penalties applied
after the race, fastest-lap points (through 2024), half points, and drivers moving
teams mid-season.

## Options considered
1. **Compute from results**: no extra source, but every edge case must be re-implemented.
2. **Snapshot official standings from Jolpica** after each ETL run.

## Decision
Option 2. Each run replaces the season's rows in `standings` with Jolpica's latest
standings and records `after_round`.

## Consequences
- Standings match official figures by construction. Two Jolpica calls per run.
- Only the latest snapshot is stored, so a standings-over-time chart would need
  computing from results or storing per-round snapshots (a possible v2 chart).

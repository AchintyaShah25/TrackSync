# 0015: Repo lives at ~/Desktop/TrackSync.nosync

- **Status:** Accepted
- **Date:** 2026-11-14
- **Milestone:** 1
- **Supersedes:** the location chosen in [0009](0009-repo-outside-icloud.md) (its rule, "keep the
  repo out of iCloud", still holds)

## Context
0009 moved the repo to `~/Developer/pitwall` to escape iCloud offloading. The owner wants
the project on the Desktop, and stored only on this Mac. The Desktop is iCloud-synced with
Optimize Mac Storage.

## Options considered
1. **Stay in `~/Developer`, with a Desktop shortcut**: no caveats, but the files are not on the Desktop.
2. **`~/Desktop/TrackSync.nosync`**: iCloud skips folders whose name ends in `.nosync`, so
   files are never uploaded or offloaded. The behavior is undocumented by Apple but long-standing.
3. **Turn off iCloud Desktop sync**: affects every file on the Mac.

## Decision
Option 2 (owner's choice). The project, including `.git`, `.env` and the OpenF1/FastF1
response caches, was copied with `rsync`. Checksums of all 2,157 files matched. `make
bootstrap` rebuilt the toolchain, and all suites passed (49 Python, 13 web, lint clean).

## Consequences
- No iCloud copy. Backups are Time Machine plus GitHub pushes.
- If a future macOS stopped honoring `.nosync`, the symptom would be silent hangs again.
  Check with `find . -flags +dataless`.
- `~/Developer/pitwall` was deleted (with the pnpm shared store `~/Library/pnpm`, which
  only held this project's first install). `~/Desktop/pitwall` is a stale, iCloud-synced
  copy kept for now: the Claude Code session that did this work runs from it.

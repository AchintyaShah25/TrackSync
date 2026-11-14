# 0009: Keep the repo outside iCloud-synced folders

- **Status:** Accepted (location superseded by [0015](0015-repo-on-desktop-nosync.md))
- **Date:** 2026-11-14
- **Milestone:** 1
- **Related:** [0003](0003-isolated-project-local-toolchain.md)

## Context
The repo started at `~/Desktop/pitwall`. On this Mac, Desktop & Documents sync to iCloud
with "Optimize Mac Storage" on. Within about 90 minutes, macOS had offloaded ~2,000 repo
files (venv, uv-managed Python, caches, and 31 source files, including `CLAUDE.md` and
`uv.lock`) as cloud-only placeholders. Reading a placeholder blocks in `read()` until it
downloads, so the symptoms looked like tool bugs: `uv sync` hung in a hatchling build
(first misdiagnosed as a parallel-build issue and worked around with
`UV_CONCURRENT_BUILDS=1`), and the API and ETL hung at import with no output.
`sample <pid>` showed `_Py_read`, `find . -flags +dataless` listed the files, and iCloud
had also created a conflict copy `.git/index 2`.

## Options considered
1. **Move the repo to `~/Developer/pitwall`** (not synced): fixes the cause, keeps 2 GB
   of tooling out of iCloud, and protects `.git` from conflict copies.
2. **Stay on Desktop and rename heavy folders to `*.nosync`**: tooling is excluded, but
   source files can still be offloaded.
3. **Turn off Optimize Mac Storage / Desktop sync**: a Mac-wide change for one project.

## Decision
Option 1 (chosen by the owner). The offloaded files were downloaded with `brctl download`,
and the project (without tooling, caches or `.git/index 2`) was copied with `rsync`.
Checksums of all 773 files matched, and `make bootstrap` rebuilt the toolchain. The
`UV_CONCURRENT_BUILDS` workaround was removed, since the real cause was iCloud.

## Consequences
- Tools no longer hang. Bootstrap takes about a minute because the downloads are cached.
- The old Desktop copy is stale and should be deleted by the owner.
- Diagnosis tip for silent hangs on macOS: check `find . -flags +dataless` first.

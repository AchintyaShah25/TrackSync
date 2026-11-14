# 0003: Isolated, project-local toolchain

- **Status:** Accepted
- **Date:** 2026-11-14
- **Milestone:** 1

## Context
The developer laptop must not be changed outside this repo: no global installs, no
shared caches or dotfiles written by project tools. The system Python is 3.9 (the
project needs 3.12) and the Supabase CLI was not installed. Docker is already present
and is the one shared tool we rely on.

## Options considered
1. **Homebrew + global installs** (`brew install supabase`, system Python 3.12): the
   usual setup, but it changes the machine and drifts from what CI runs.
2. **Dev container**: fully isolated, but heavier and slower to iterate, and the
   Supabase CLI inside a container needs Docker-in-Docker.
3. **Everything repo-local, wired through the Makefile**: uv-managed CPython and its
   cache in `.tools/`, a project `.venv`, pnpm store in `.tools/pnpm-store`, the
   Supabase CLI as an npm devDependency, and its home dir and FastF1 cache in the repo.

## Decision
Option 3. The Makefile exports `UV_PYTHON_INSTALL_DIR`, `UV_CACHE_DIR`,
`UV_PYTHON_PREFERENCE=only-managed`, `SUPABASE_HOME`, `SUPABASE_TELEMETRY_DISABLED`,
`DO_NOT_TRACK`, `FASTF1_CACHE` and `OPENF1_CACHE_DIR`; `pnpm-workspace.yaml` sets `storeDir`.
`make bootstrap` sets everything up and `make clean-tools` removes it.

## Consequences
- Deleting the repo removes everything. CI uses the same versions (uv lockfile, pnpm lockfile).
- Pitfalls found while setting this up: `uv python install` drops a shim in `~/.local/bin`
  unless given `--no-bin`; pnpm 11 ignores `store-dir` in `.npmrc` (use
  `pnpm-workspace.yaml`); the Supabase CLI writes `~/.supabase` unless `SUPABASE_HOME` is set; FastF1 writes
  `~/Library/Caches/fastf1` unless `FASTF1_CACHE` is set.
- The repo must not live in an iCloud-synced folder: offloaded files make tools hang
  (see [0009](0009-repo-outside-icloud.md)).
- Run commands through `make` (or export the same variables). Calling `uv`/`supabase`
  by hand without them falls back to user-level locations.
- Docker images and volumes are still managed by the shared Docker daemon, namespaced by
  `project_id = "pitwall"` and the compose project name.

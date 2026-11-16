#!/bin/bash
# Daily knowledge-base embedding backfill for the LOCAL database (decision 0037).
#
# Gemini's free tier embeds 1000 texts a day (decision 0034), so the first full build
# takes several days: run `make rag-backfill` once a day until it reports 0 left. (Not
# scheduled: macOS blocks background jobs from reading ~/Desktop, see decision 0037.)
# Each run:
#   1. skips if the local Supabase database is not running;
#   2. runs `tracksync-etl --rag`, which embeds up to the daily quota and stops;
#   3. once every chunk has a vector, re-runs the chat eval once, so README scores reflect
#      full hybrid retrieval. Previous agent answers are kept (--retry-errors).
# Output goes to .cache/rag-backfill.log. Always targets the local database, never
# production, whatever .env says.
set -uo pipefail

cd "$(dirname "$0")/.." || exit 1
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
LOCAL_DB="postgresql://postgres:postgres@127.0.0.1:54322/postgres"
DB_CONTAINER="supabase_db_tracksync"

mkdir -p .cache
exec >>.cache/rag-backfill.log 2>&1
echo "=== $(date '+%Y-%m-%d %H:%M:%S %Z')"

# One run at a time (a wake-up can fire while a run is still going).
LOCK=.cache/rag-backfill.lock
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "another run is in progress; skipped"
  exit 0
fi
trap 'rmdir "$LOCK"' EXIT

if ! docker exec "$DB_CONTAINER" pg_isready -q 2>/dev/null; then
  echo "local database is not running; skipped"
  exit 0
fi

missing() {
  docker exec "$DB_CONTAINER" psql -U postgres -Atc \
    "select count(*) filter (where embedding is null) from rag_chunks"
}

before=$(missing)
echo "chunks without embeddings: $before"
if [ "$before" = "0" ] && [ -f .cache/rag-backfill.done ]; then
  echo "backfill complete; nothing to do"
  exit 0
fi

# Keys (GEMINI_API_KEY, GROQ_API_KEY) come from .env; the database is forced to local.
set -a
# shellcheck disable=SC1091
[ -f .env ] && . ./.env
set +a
export DATABASE_URL="$LOCAL_DB"

if [ "$before" != "0" ]; then
  uv run --package tracksync-etl tracksync-etl --rag || echo "etl exited with $?"
fi

after=$(missing)
echo "chunks without embeddings now: $after"
if [ "$after" = "0" ] && [ ! -f .cache/rag-backfill.done ]; then
  echo "all chunks embedded; re-running the chat eval once"
  if uv run --package tracksync-api python evals/chat/run_eval.py --agent --retry-errors; then
    touch .cache/rag-backfill.done
  else
    echo "eval below target or failed (exit $?); will retry on the next run"
  fi
fi

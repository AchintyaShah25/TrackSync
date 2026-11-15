"""Shared pytest fixtures for all Python packages.

`fresh_database(name)` creates (once per run) a dedicated database on the local
Supabase Postgres, applies supabase/migrations, and yields its URL. Tests that need it
are marked `db` and are skipped when Postgres is not running (`make db-up`).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).parent
ADMIN_URL = os.environ.get(
    "TEST_DATABASE_ADMIN_URL", "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
)


def _connect(url: str, **kw):
    import psycopg

    return psycopg.connect(url, connect_timeout=3, **kw)


def _create_database(name: str) -> str:
    try:
        admin = _connect(ADMIN_URL, autocommit=True)
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"local Postgres not reachable ({exc}); run `make db-up`")
    with admin:
        admin.execute(f"drop database if exists {name} with (force)")
        admin.execute(f"create database {name}")
    url = ADMIN_URL.rsplit("/", 1)[0] + f"/{name}"
    with _connect(url, autocommit=True) as conn:
        for sql in sorted((ROOT / "supabase" / "migrations").glob("*.sql")):
            conn.execute(sql.read_text())
    return url


@pytest.fixture(scope="session")
def fresh_database():
    """Factory: create (once per name per run) a migrated database and return its URL."""
    created: dict[str, str] = {}

    def make(name: str) -> str:
        if name not in created:
            created[name] = _create_database(name)
        return created[name]

    return make


@pytest.fixture(scope="session")
def test_db_url(fresh_database) -> str:
    """Migrated database for the ETL tests."""
    return fresh_database("tracksync_test_etl")

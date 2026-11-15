"""Row-level security on user-owned tables, checked directly in Postgres (SPEC M3 acceptance)."""

import json
import uuid

import psycopg
import pytest

pytestmark = pytest.mark.db

A = str(uuid.uuid4())
B = str(uuid.uuid4())
SAVE = "insert into saved_items (user_id, kind, title, path) values (%s, 'chart', %s, %s)"


@pytest.fixture(scope="module")
def db(fresh_database) -> str:
    url = fresh_database("tracksync_test_rls")
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("insert into auth.users (id) values (%s), (%s)", (A, B))
    return url


def as_user(conn: psycopg.Connection, user_id: str | None) -> None:
    """Act like a Supabase request: role + JWT claims, scoped to the current transaction."""
    if user_id is None:
        conn.execute("set local role anon")
        return
    conn.execute("set local role authenticated")
    conn.execute(
        "select set_config('request.jwt.claims', %s, true)",
        (json.dumps({"sub": user_id, "role": "authenticated"}),),
    )


def test_users_only_see_and_change_their_own_rows(db):
    """User B cannot read, update or delete user A's preferences or saved items.

    Why: SPEC M3 acceptance ("a user cannot read another user's rows"); these tables
    are reachable directly with the public anon key, so RLS is the real boundary.
    """
    with psycopg.connect(db) as conn:
        with conn.transaction():
            as_user(conn, A)
            conn.execute(
                "insert into user_preferences (user_id, units) values (%s, 'imperial')", (A,)
            )
            conn.execute(SAVE, (A, "Monza", "/races/2024/16"))
        with conn.transaction():
            as_user(conn, B)
            assert conn.execute("select count(*) from user_preferences").fetchone() == (0,)
            assert conn.execute("select count(*) from saved_items").fetchone() == (0,)
            assert conn.execute("update saved_items set title = 'pwned'").rowcount == 0
            assert conn.execute("delete from user_preferences").rowcount == 0
        with conn.transaction():
            as_user(conn, A)
            assert conn.execute("select title from saved_items").fetchall() == [("Monza",)]
            assert conn.execute("select units from user_preferences").fetchone() == ("imperial",)


def test_users_cannot_write_rows_for_someone_else(db):
    """Inserting a row with another user's id is rejected by the policy's WITH CHECK.

    Why: without it, B could plant saved items into A's account.
    """
    with (
        psycopg.connect(db) as conn,
        pytest.raises(psycopg.errors.InsufficientPrivilege),
        conn.transaction(),
    ):
        as_user(conn, B)
        conn.execute(SAVE, (A, "x", "/x"))


def test_anonymous_visitors_see_no_user_data_or_usage(db):
    """The anon role is denied user tables and usage counters but can read the public
    knowledge base.

    Why: the anon key ships in the browser bundle; anything it can read is public.
    """
    with psycopg.connect(db, autocommit=True) as admin:
        admin.execute(
            "insert into usage_counters (key, day, count) values ('chat:all', current_date, 3)"
        )
    with psycopg.connect(db) as conn:
        with conn.transaction():
            as_user(conn, None)
            assert conn.execute("select count(*) from rag_chunks").fetchone() == (0,)
        for table in ("user_preferences", "saved_items", "usage_counters"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
                as_user(conn, None)
                conn.execute(f"select * from {table}")


def test_signed_in_users_cannot_read_usage_counters(db):
    """Even signed-in users cannot read or reset the chat usage counters.

    Why: the daily chat limits live there; a client able to write them could lift its
    own limit.
    """
    with (
        psycopg.connect(db) as conn,
        pytest.raises(psycopg.errors.InsufficientPrivilege),
        conn.transaction(),
    ):
        as_user(conn, A)
        conn.execute("delete from usage_counters")


def test_saved_item_paths_must_be_site_paths(db):
    """Saved items only store site-relative paths, not arbitrary URLs.

    Why: saved paths are rendered as links; an absolute or javascript: URL would be an
    open redirect or XSS vector.
    """
    with (
        psycopg.connect(db) as conn,
        pytest.raises(psycopg.errors.CheckViolation),
        conn.transaction(),
    ):
        as_user(conn, A)
        conn.execute(SAVE, (A, "x", "javascript:alert(1)"))

"""Every allow-listed query_stats query against the seeded test database, plus auth caching."""

import pytest
from app.auth import AuthVerifier
from app.services.chat.stats import QUERIES, StatsContext, StatsError, run_query
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.db

CASES = {
    "race_result": ({"season": 2024, "race": "monza"},
                    lambda r: r["classification"][0]["driver"] == "Charles Leclerc"),
    "qualifying_result": ({"season": 2024, "race": "16"}, lambda r: r["qualifying"]),
    "driver_season": ({"season": 2024, "driver": "LEC"}, lambda r: r["totals"]["wins"] == 1),
    "standings": ({"season": 2024, "kind": "driver"}, lambda r: r["standings"]),
    "head_to_head": ({"season": 2024, "driver_a": "Leclerc", "driver_b": "NOR"},
                     lambda r: r["races_finished_ahead"]["LEC"] == 1),
    "race_strategy": ({"season": 2024, "race": "Italy"},
                      lambda r: r["strategies"][0]["stops"] >= 1),
    "safety_cars": ({"season": 2024, "race": "Monza"}, lambda r: isinstance(r["periods"], list)),
    "wins": ({"driver": "leclerc"}, lambda r: r["total_wins"] == 1),
    "lap_times": ({"season": 2024, "race": "Monza", "drivers": ["LEC"]}, lambda r: r["drivers"]),
    "next_race": ({}, lambda r: "next" in r or "last" in r),
}  # fmt: skip


@pytest.fixture
async def ctx(api_db_url):
    engine = create_async_engine(api_db_url.replace("postgresql://", "postgresql+asyncpg://", 1))
    async with engine.connect() as conn:
        yield StatsContext(conn)
    await engine.dispose()


def test_every_query_has_a_case():
    """The table above covers the whole allow-list.

    Why: a new query added without a test would ship unverified SQL.
    """
    assert set(CASES) == set(QUERIES)


@pytest.mark.parametrize("name", sorted(CASES))
async def test_query_runs_on_seeded_data(ctx, name):
    """Each allow-listed query resolves names and returns the expected shape.

    Why: these queries are the only source of numbers in chat answers (SPEC M3).
    """
    params, check = CASES[name]
    result = await run_query(ctx, name, params)
    assert check(result), result


async def test_query_params_are_validated(ctx):
    """Unknown parameters are ignored, numbers are checked, unknown queries rejected.

    Why: parameters come from the model; nothing it sends may reach SQL unvalidated.
    """
    ok = await run_query(ctx, "standings", {"season": "2024", "evil": "'; drop table x;--"})
    assert ok["season"] == 2024
    with pytest.raises(StatsError, match="must be a number"):
        await run_query(ctx, "standings", {"season": "twenty"})
    with pytest.raises(StatsError, match="unknown query"):
        await run_query(ctx, "raw_sql", {"sql": "select 1"})
    with pytest.raises(StatsError, match="no data for season 1999"):
        await run_query(ctx, "standings", {"season": 1999})


async def test_auth_verifier_caches_and_maps_statuses():
    """Valid tokens are cached (one auth-server call), rejected ones return None, outages 503.

    Why: the API checks tokens with Supabase on each request; caching keeps that cheap and
    an auth outage must not look like "signed out".
    """
    calls = []

    def server(url, headers, timeout):
        calls.append(headers["Authorization"])
        return {"Bearer ok": (200, b'{"id": "u1", "email": "a@b.c"}'),
                "Bearer old": (401, b"{}")}.get(headers["Authorization"], (500, b""))  # fmt: skip

    v = AuthVerifier("https://x.supabase.co", "anon", transport=server)
    assert (await v.verify("ok")).id == "u1"
    assert (await v.verify("ok")).email == "a@b.c" and calls.count("Bearer ok") == 1
    assert await v.verify("old") is None
    with pytest.raises(HTTPException) as err:
        await v.verify("boom")
    assert err.value.status_code == 503

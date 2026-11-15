"""/me endpoints: preferences and saved items, isolated per user by RLS (SPEC M3)."""

import uuid

import httpx
import psycopg
import pytest
from app.auth import AuthVerifier
from app.config import Settings
from app.main import create_app

from .conftest import SEED

pytestmark = pytest.mark.db

A, B = str(uuid.uuid4()), str(uuid.uuid4())
TOKENS = {"Bearer token-a": A, "Bearer token-b": B}
HA, HB = {"Authorization": "Bearer token-a"}, {"Authorization": "Bearer token-b"}


@pytest.fixture(scope="module")
def me_db(fresh_database) -> str:
    url = fresh_database("tracksync_test_me")
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(SEED.read_text())
        conn.execute("insert into auth.users (id) values (%s), (%s)", (A, B))
    return url


@pytest.fixture(scope="module")
async def mc(me_db):
    app = create_app(Settings(database_url=me_db, web_origin="http://localhost:3000"))
    async with app.router.lifespan_context(app):

        def auth_server(url, headers, timeout):
            uid = TOKENS.get(headers["Authorization"])
            return (200, f'{{"id": "{uid}"}}'.encode()) if uid else (401, b"{}")

        app.state.auth = AuthVerifier("https://auth.test", "anon", transport=auth_server)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


async def test_me_requires_sign_in(mc):
    """No token or an unknown token gets 401 on every /me route.

    Why: these routes expose personal data.
    """
    assert (await mc.get("/me/preferences")).status_code == 401
    assert (await mc.get("/me/saved", headers={"Authorization": "Bearer nope"})).status_code == 401


async def test_preferences_round_trip_and_validation(mc):
    """Defaults before saving, then exactly what was saved; unknown drivers are rejected.

    Why: preferences drive defaults across the site (favorite driver, units, chat level).
    """
    r = await mc.get("/me/preferences", headers=HA)
    assert r.json()["units"] == "metric" and r.headers["cache-control"] == "private, no-store"
    prefs = {"favorite_driver_id": "leclerc", "units": "imperial", "chat_level": "expert"}
    assert (await mc.put("/me/preferences", json=prefs, headers=HA)).status_code == 200
    got = (await mc.get("/me/preferences", headers=HA)).json()
    assert got["favorite_driver_id"] == "leclerc" and got["units"] == "imperial"
    bad = await mc.put("/me/preferences", json={"favorite_driver_id": "nobody"}, headers=HA)
    assert bad.status_code == 422
    assert (await mc.get("/me/preferences", headers=HB)).json()["favorite_driver_id"] is None


async def test_saved_items_are_private_to_their_owner(mc):
    """B never sees, deletes or pins A's saved items, even knowing the id.

    Why: SPEC M3 acceptance ("a user cannot read another user's rows"), through the API.
    """
    item = {"kind": "strategy", "title": "Monza one-stop", "path": "/races/2024/16/forecast?d=PIA"}
    created = await mc.post("/me/saved", json=item, headers=HA)
    assert created.status_code == 201
    item_id = created.json()["id"]
    assert [i["id"] for i in (await mc.get("/me/saved", headers=HA)).json()] == [item_id]
    assert (await mc.get("/me/saved", headers=HB)).json() == []
    assert (await mc.delete(f"/me/saved/{item_id}", headers=HB)).status_code == 404
    pin = await mc.put("/me/preferences", json={"home_widgets": [item_id]}, headers=HB)
    assert pin.status_code == 422
    assert (
        await mc.put("/me/preferences", json={"home_widgets": [item_id]}, headers=HA)
    ).status_code == 200
    assert (await mc.delete(f"/me/saved/{item_id}", headers=HA)).status_code == 204
    # Deleting a pinned item also unpins it.
    assert (await mc.get("/me/preferences", headers=HA)).json()["home_widgets"] == []


@pytest.mark.parametrize(
    "path", ["https://evil.example/x", "//evil.example", "javascript:alert(1)", "/a\\b"]
)
async def test_saved_paths_must_stay_on_site(mc, path):
    """Only site-relative paths can be saved.

    Why: saved items render as links; anything else is an open redirect or XSS vector.
    """
    r = await mc.post("/me/saved", json={"kind": "chart", "title": "x", "path": path}, headers=HA)
    assert r.status_code == 422


async def test_saved_items_are_capped(mc):
    """A user can keep at most 100 saved items.

    Why: a bound on per-user rows keeps the free database small and abuse cheap.
    """
    for i in range(100):
        r = await mc.post(
            "/me/saved", json={"kind": "chart", "title": f"c{i}", "path": "/"}, headers=HB
        )
        assert r.status_code == 201
    over = await mc.post(
        "/me/saved", json={"kind": "chart", "title": "one more", "path": "/"}, headers=HB
    )
    assert over.status_code == 409

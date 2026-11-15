import httpx
import pytest
from app.config import Settings
from app.main import create_app

pytestmark = pytest.mark.db


async def test_health_reports_ok_with_database(client):
    """GET /health returns ok and a reachable database.

    Why: Render's health check and the web app's wake-up ping depend on it.
    """
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": "ok"}


async def test_cors_allows_only_the_web_origin(client):
    """CORS echoes the configured web origin and rejects others.

    Why: SPEC section 7 restricts the API to our own frontend.
    """
    ok = await client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"
    bad = await client.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in bad.headers


async def test_health_stays_up_when_database_is_unreachable():
    """GET /health returns 200 with database="unavailable" when Postgres refuses us.

    Why: the first production deploy failed because a bad DATABASE_URL made /health
    return 500. Render then marked the service unhealthy and kept retrying, and the
    retries tripped Supabase's auth circuit breaker. Liveness must not depend on the DB.
    """
    app = create_app(
        Settings(database_url="postgresql://nobody:wrong@127.0.0.1:1/none", db_pool_size=1)
    )
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": "unavailable"}

import pytest

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

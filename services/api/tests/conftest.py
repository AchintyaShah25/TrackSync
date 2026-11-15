from pathlib import Path

import httpx
import psycopg
import pytest
from app.config import Settings
from app.main import create_app

SEED = Path(__file__).parent / "seed.sql"


@pytest.fixture(scope="session")
def api_db_url(fresh_database) -> str:
    url = fresh_database("tracksync_test_api")
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(SEED.read_text())
    return url


@pytest.fixture(scope="session")
async def client(api_db_url):
    """HTTP client against the real app (lifespan included) on the seeded test DB."""
    app = create_app(Settings(database_url=api_db_url, web_origin="http://localhost:3000"))
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c

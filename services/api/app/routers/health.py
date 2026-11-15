from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

router = APIRouter(tags=["health"])


class Health(BaseModel):
    status: str
    database: str


@router.get("/health", response_model=Health)
async def health(request: Request) -> Health:
    """Liveness + DB check. Render's health check and the web app's wake-up ping use this.

    The connection is opened inside the try (not via the get_conn dependency) so a
    database outage still returns 200 with database="unavailable". A 500 here would make
    Render restart a healthy process and keep retrying, which against Supabase's pooler
    trips its auth circuit breaker.
    """
    engine: AsyncEngine = request.app.state.engine
    try:
        async with engine.connect() as conn:
            await conn.execute(text("select 1"))
        db = "ok"
    except Exception:
        db = "unavailable"
    return Health(status="ok", database=db)

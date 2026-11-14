from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from ..db import get_conn

router = APIRouter(tags=["health"])


class Health(BaseModel):
    status: str
    database: str


@router.get("/health", response_model=Health)
async def health(conn: AsyncConnection = Depends(get_conn)) -> Health:
    """Liveness + DB check. Render's health check and the web app's wake-up ping use this."""
    try:
        await conn.execute(text("select 1"))
        db = "ok"
    except Exception:
        db = "unavailable"
    return Health(status="ok", database=db)

"""Async SQLAlchemy engine and a connection dependency."""

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from .config import Settings


def make_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        settings.async_database_url,
        pool_size=settings.db_pool_size,
        max_overflow=2,
        pool_pre_ping=True,
        # Supabase's pooler (PgBouncer, transaction mode) does not support prepared
        # statement caching.
        connect_args={"statement_cache_size": 0, "prepared_statement_cache_size": 0},
    )


async def get_conn(request: Request) -> AsyncIterator[AsyncConnection]:
    engine: AsyncEngine = request.app.state.engine
    async with engine.connect() as conn:
        yield conn

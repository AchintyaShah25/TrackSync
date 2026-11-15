"""TrackSync API: serves precomputed F1 data from Postgres. No FastF1 here (rule 1)."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from .config import Settings, get_settings
from .db import make_engine
from .ratelimit import SimulateLimiter
from .routers import circuits, events, health, seasons, standings, strategy


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level.upper())

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.engine = make_engine(settings)
        yield
        await app.state.engine.dispose()

    app = FastAPI(
        title="TrackSync API",
        version="0.1.0",
        description="Unofficial F1 analytics. Not affiliated with Formula 1 or the FIA.",
        lifespan=lifespan,
    )
    app.state.simulate_limiter = SimulateLimiter.create(
        settings.simulate_per_minute, settings.simulate_global_per_minute
    )
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    for module in (health, seasons, events, standings, circuits, strategy):
        app.include_router(module.router)
    return app


app = create_app()

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncConnection

from ..caching import public_cache
from ..db import get_conn
from ..schemas.common import AnySession, RaceSession, TraceSession
from ..schemas.events import (
    EventDetail,
    LapsPage,
    ResultRow,
    StrategyResponse,
    TracesResponse,
)
from ..services import events as service

router = APIRouter(prefix="/events", tags=["events"], dependencies=[Depends(public_cache)])
Conn = Annotated[AsyncConnection, Depends(get_conn)]


async def _require_event(event_id: int, conn: AsyncConnection) -> None:
    if not await service.event_exists(conn, event_id):
        raise HTTPException(404, f"event {event_id} not found")


def _split(value: str | None) -> list[str]:
    return [v.strip() for v in (value or "").split(",") if v.strip()]


@router.get("/{event_id}", response_model=EventDetail)
async def get_event(event_id: int, conn: Conn):
    event = await service.get_event(conn, event_id)
    if event is None:
        raise HTTPException(404, f"event {event_id} not found")
    return event


@router.get("/{event_id}/results", response_model=list[ResultRow])
async def get_results(event_id: int, conn: Conn, session: AnySession = "R"):
    await _require_event(event_id, conn)
    return await service.get_results(conn, event_id, session)


@router.get("/{event_id}/laps", response_model=LapsPage)
async def get_laps(
    event_id: int,
    conn: Conn,
    session: RaceSession = "R",
    drivers: Annotated[str | None, Query(description="comma-separated driver ids")] = None,
    limit: Annotated[int, Query(ge=1, le=2000)] = 500,
    cursor: str | None = None,
):
    await _require_event(event_id, conn)
    if cursor is not None and not cursor.rpartition(":")[2].isdigit():
        raise HTTPException(422, "invalid cursor")
    return await service.get_laps(conn, event_id, session, _split(drivers) or None, limit, cursor)


@router.get("/{event_id}/stints", response_model=StrategyResponse)
async def get_stints(event_id: int, conn: Conn, session: RaceSession = "R"):
    await _require_event(event_id, conn)
    return await service.get_strategy(conn, event_id, session)


@router.get("/{event_id}/traces", response_model=TracesResponse)
async def get_traces(
    event_id: int,
    conn: Conn,
    drivers: Annotated[str, Query(description="comma-separated driver codes, e.g. VER,NOR")],
    session: TraceSession = "Q",
):
    codes = _split(drivers)
    if not codes:
        raise HTTPException(422, "give at least one driver code")
    if len(codes) > service.MAX_TRACE_DRIVERS:
        raise HTTPException(422, f"at most {service.MAX_TRACE_DRIVERS} drivers")
    traces = await service.get_traces(conn, event_id, session, codes)
    if traces is None:
        raise HTTPException(404, f"event {event_id} not found")
    return traces

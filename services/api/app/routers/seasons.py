from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncConnection

from ..caching import public_cache
from ..db import get_conn
from ..schemas.seasons import EventSummary, Season
from ..services import seasons as service

router = APIRouter(tags=["seasons"], dependencies=[Depends(public_cache)])


@router.get("/seasons", response_model=list[Season])
async def list_seasons(conn: AsyncConnection = Depends(get_conn)):
    return await service.list_seasons(conn)


@router.get("/seasons/{year}/events", response_model=list[EventSummary])
async def list_events(
    year: int = Path(ge=1950, le=2100), conn: AsyncConnection = Depends(get_conn)
):
    events = await service.list_events(conn, year)
    if events is None:
        raise HTTPException(404, f"season {year} not found")
    return events

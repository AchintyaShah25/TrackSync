from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncConnection

from ..caching import public_cache
from ..db import get_conn
from ..schemas.standings import StandingsResponse
from ..services import standings as service

router = APIRouter(tags=["standings"], dependencies=[Depends(public_cache)])


@router.get("/standings/{year}", response_model=StandingsResponse)
async def get_standings(
    year: int = Path(ge=1950, le=2100), conn: AsyncConnection = Depends(get_conn)
):
    standings = await service.get_standings(conn, year)
    if standings is None:
        raise HTTPException(404, f"no standings for {year}")
    return standings

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncConnection

from ..caching import public_cache
from ..db import get_conn
from ..ratelimit import limit_simulate
from ..schemas.strategy import ModelSummary, SimulateRequest, SimulateResponse
from ..services import strategy as service

router = APIRouter(prefix="/strategy", tags=["strategy"])
Conn = Annotated[AsyncConnection, Depends(get_conn)]


@router.post(
    "/simulate",
    response_model=SimulateResponse,
    dependencies=[Depends(limit_simulate)],
    summary="Monte Carlo comparison of up to 3 strategies against the driver's real one",
)
async def simulate(body: SimulateRequest, conn: Conn):
    try:
        return await service.simulate_strategies(conn, body)
    except service.StrategyError as exc:
        raise HTTPException(exc.status, exc.detail) from exc


@router.get(
    "/params/{circuit_id}",
    response_model=ModelSummary,
    dependencies=[Depends(public_cache)],
    summary="Fitted race-model summary for a circuit (degradation curves, pit loss, SC rates)",
)
async def params(circuit_id: str, conn: Conn):
    try:
        return await service.model_summary(conn, circuit_id)
    except service.StrategyError as exc:
        raise HTTPException(404 if exc.status == 422 else exc.status, exc.detail) from exc

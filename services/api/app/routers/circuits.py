from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncConnection

from ..caching import public_cache
from ..db import get_conn
from ..schemas.circuits import Circuit
from ..services import circuits as service

router = APIRouter(tags=["circuits"], dependencies=[Depends(public_cache)])


@router.get("/circuits/{circuit_id}", response_model=Circuit)
async def get_circuit(circuit_id: str, conn: AsyncConnection = Depends(get_conn)):
    circuit = await service.get_circuit(conn, circuit_id)
    if circuit is None:
        raise HTTPException(404, f"circuit {circuit_id} not found")
    return circuit

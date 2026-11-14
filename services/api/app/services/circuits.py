from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from ..schemas.circuits import Circuit


async def get_circuit(conn: AsyncConnection, circuit_id: str) -> Circuit | None:
    row = (
        await conn.execute(
            text(
                """
                select id, name, locality, country, length_m, outline,
                       coalesce(corners, '[]'::jsonb) as corners
                from circuits where id = :id
                """
            ),
            {"id": circuit_id},
        )
    ).first()
    return Circuit.model_validate(row._mapping) if row else None

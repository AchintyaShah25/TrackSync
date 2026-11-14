"""Shared query fragments."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from ..schemas.common import DriverRef

# Drivers who took part in an event, with the team they drove for there.
EVENT_DRIVERS = text(
    """
    select distinct on (d.id)
           d.id, d.code, d.full_name, d.number, r.team_id, t.name as team_name, t.color_hex
    from results r
    join drivers d on d.id = r.driver_id
    join events e on e.id = r.event_id
    left join teams t on t.id = r.team_id and t.season = e.season
    where r.event_id = :event_id
    order by d.id, (r.session = 'R') desc
    """
)


def driver_ref(row) -> DriverRef:
    return DriverRef(
        id=row.id,
        code=row.code,
        full_name=row.full_name,
        number=row.number,
        team_id=row.team_id,
        team_name=row.team_name,
        color_hex=row.color_hex,
    )


async def event_drivers(conn: AsyncConnection, event_id: int) -> dict[str, DriverRef]:
    rows = (await conn.execute(EVENT_DRIVERS, {"event_id": event_id})).all()
    return {r.id: driver_ref(r) for r in rows}

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from ..schemas.seasons import EventSummary, Season

COMPLETED = "e.race_start_utc < now() - interval '4 hours'"

EVENT_COLUMNS = """
    e.id, e.season, e.round, e.name, e.slug, e.format, e.circuit_id,
    c.name as circuit_name, c.locality, c.country, e.race_start_utc, e.sessions,
    exists (select 1 from results r where r.event_id = e.id and r.session = 'R') as has_data
"""


async def list_seasons(conn: AsyncConnection) -> list[Season]:
    rows = await conn.execute(
        text(
            f"""
            select s.year, count(e.id) as events,
                   count(e.id) filter (where {COMPLETED}) as completed
            from seasons s left join events e on e.season = s.year
            group by s.year order by s.year desc
            """
        )
    )
    return [Season(year=r.year, events=r.events, completed=r.completed) for r in rows]


async def list_events(conn: AsyncConnection, year: int) -> list[EventSummary] | None:
    exists = await conn.execute(text("select 1 from seasons where year = :y"), {"y": year})
    if exists.first() is None:
        return None
    rows = await conn.execute(
        text(
            f"""
            select {EVENT_COLUMNS}
            from events e join circuits c on c.id = e.circuit_id
            where e.season = :y order by e.round
            """
        ),
        {"y": year},
    )
    return [EventSummary.model_validate(r._mapping) for r in rows]

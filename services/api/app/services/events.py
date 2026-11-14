from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from ..schemas.events import (
    EventDetail,
    LapRow,
    LapsPage,
    ResultRow,
    StintRow,
    StrategyResponse,
    Trace,
    TracesResponse,
)
from .common import event_drivers
from .seasons import EVENT_COLUMNS

MAX_TRACE_DRIVERS = 3


async def get_event(conn: AsyncConnection, event_id: int) -> EventDetail | None:
    row = (
        await conn.execute(
            text(
                f"""
                select {EVENT_COLUMNS},
                  (select coalesce(array_agg(distinct session), '{{}}') from results
                   where event_id = e.id) as data_sessions,
                  (select coalesce(array_agg(distinct session), '{{}}') from fastest_lap_traces
                   where event_id = e.id) as trace_sessions,
                  (select max(lap) from laps where event_id = e.id and session = 'R') as total_laps
                from events e join circuits c on c.id = e.circuit_id
                where e.id = :id
                """
            ),
            {"id": event_id},
        )
    ).first()
    if row is None:
        return None
    drivers = await event_drivers(conn, event_id)
    order = (
        await conn.execute(
            text(
                """
                select driver_id from results where event_id = :id
                order by (session = 'R') desc, position nulls last, driver_id
                """
            ),
            {"id": event_id},
        )
    ).scalars()
    ordered = list(dict.fromkeys(d for d in order if d in drivers))
    data = dict(row._mapping)
    data["data_sessions"] = sorted(data["data_sessions"])
    data["trace_sessions"] = sorted(data["trace_sessions"])
    return EventDetail(**data, drivers=[drivers[d] for d in ordered])


async def event_exists(conn: AsyncConnection, event_id: int) -> bool:
    row = await conn.execute(text("select 1 from events where id = :id"), {"id": event_id})
    return row.first() is not None


async def get_results(conn: AsyncConnection, event_id: int, session: str) -> list[ResultRow]:
    drivers = await event_drivers(conn, event_id)
    rows = await conn.execute(
        text(
            """
            select driver_id, position, grid, points, status, time_ms from results
            where event_id = :id and session = :s
            order by position nulls last, driver_id
            """
        ),
        {"id": event_id, "s": session},
    )
    return [
        ResultRow(
            position=r.position,
            driver=drivers[r.driver_id],
            grid=r.grid,
            points=r.points,
            status=r.status,
            time_ms=r.time_ms,
        )
        for r in rows
        if r.driver_id in drivers
    ]


def _parse_cursor(cursor: str | None) -> tuple[str, int]:
    if not cursor:
        return "", 0
    driver, _, lap = cursor.rpartition(":")
    return driver, int(lap)


async def get_laps(
    conn: AsyncConnection,
    event_id: int,
    session: str,
    drivers: list[str] | None,
    limit: int,
    cursor: str | None,
) -> LapsPage:
    """Keyset pagination on (driver_id, lap)."""
    after_driver, after_lap = _parse_cursor(cursor)
    rows = (
        await conn.execute(
            text(
                """
                select driver_id, lap, lap_time_ms, compound, tyre_life, stint, position,
                       pit_in, pit_out, track_status, is_accurate
                from laps
                where event_id = :id and session = :s
                  and (cast(:drivers as text[]) is null
                       or driver_id = any(cast(:drivers as text[])))
                  and (driver_id, lap) > (:after_driver, :after_lap)
                order by driver_id, lap
                limit :limit
                """
            ),
            {
                "id": event_id,
                "s": session,
                "drivers": drivers,
                "after_driver": after_driver,
                "after_lap": after_lap,
                "limit": limit + 1,
            },
        )
    ).all()
    items = [LapRow.model_validate(r._mapping) for r in rows[:limit]]
    next_cursor = f"{items[-1].driver_id}:{items[-1].lap}" if len(rows) > limit else None
    return LapsPage(items=items, next_cursor=next_cursor)


async def get_strategy(conn: AsyncConnection, event_id: int, session: str) -> StrategyResponse:
    drivers = await event_drivers(conn, event_id)
    finish = dict(
        (
            await conn.execute(
                text(
                    """
                    select driver_id, position from results
                    where event_id = :id and session = :s
                    """
                ),
                {"id": event_id, "s": session},
            )
        ).all()
    )
    stints = [
        StintRow.model_validate(r._mapping)
        for r in await conn.execute(
            text(
                """
                select driver_id, stint, compound, start_lap, end_lap from stints
                where event_id = :id and session = :s order by driver_id, stint
                """
            ),
            {"id": event_id, "s": session},
        )
    ]
    total = (
        await conn.execute(
            text("select max(lap) from laps where event_id = :id and session = :s"),
            {"id": event_id, "s": session},
        )
    ).scalar()
    with_stints = {s.driver_id for s in stints}
    ordered = sorted(
        (d for d in drivers.values() if d.id in with_stints),
        key=lambda d: (finish.get(d.id) is None, finish.get(d.id) or 99, d.code),
    )
    return StrategyResponse(
        session=session,
        total_laps=total or max((s.end_lap for s in stints), default=0),
        drivers=ordered,
        finish_position={d.id: finish.get(d.id) for d in ordered},
        stints=[s for s in stints if s.driver_id in drivers],
    )


async def get_traces(
    conn: AsyncConnection, event_id: int, session: str, codes: list[str]
) -> TracesResponse | None:
    """Traces for up to MAX_TRACE_DRIVERS drivers, selected by 3-letter code (e.g. VER)."""
    circuit = (
        await conn.execute(text("select circuit_id from events where id = :id"), {"id": event_id})
    ).scalar()
    if circuit is None:
        return None
    drivers = await event_drivers(conn, event_id)
    by_code = {d.code.upper(): d for d in drivers.values()}
    wanted = [by_code[c] for c in dict.fromkeys(c.upper() for c in codes) if c in by_code]
    rows = (
        await conn.execute(
            text(
                """
                select driver_id, lap, lap_time_ms, points from fastest_lap_traces
                where event_id = :id and session = :s and driver_id = any(:ids)
                """
            ),
            {"id": event_id, "s": session, "ids": [d.id for d in wanted]},
        )
    ).all()
    by_id = {r.driver_id: r for r in rows}
    traces = [
        Trace(
            driver=d,
            lap=by_id[d.id].lap,
            lap_time_ms=by_id[d.id].lap_time_ms,
            points=by_id[d.id].points,
        )
        for d in wanted
        if d.id in by_id
    ]
    return TracesResponse(event_id=event_id, session=session, circuit_id=circuit, traces=traces)

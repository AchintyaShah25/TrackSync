from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from ..schemas.common import DriverRef
from ..schemas.standings import ConstructorStanding, DriverStanding, StandingsResponse


async def get_standings(conn: AsyncConnection, season: int) -> StandingsResponse | None:
    rows = (
        await conn.execute(
            text(
                """
                select s.kind, s.entity_id, s.position, s.points, s.wins, s.after_round,
                       d.code, d.full_name, d.number,
                       dt.team_id as driver_team_id, dteam.name as driver_team_name,
                       dteam.color_hex as driver_color,
                       t.name as team_name, t.color_hex as team_color
                from standings s
                left join drivers d on s.kind = 'driver' and d.id = s.entity_id
                left join lateral (
                    -- the team the driver raced for most recently that season
                    select r.team_id from results r join events e on e.id = r.event_id
                    where r.driver_id = s.entity_id and e.season = s.season
                    order by e.round desc limit 1
                ) dt on s.kind = 'driver'
                left join teams dteam on dteam.id = dt.team_id and dteam.season = s.season
                left join teams t on s.kind = 'constructor' and t.id = s.entity_id
                                 and t.season = s.season
                where s.season = :y
                order by s.kind, s.position nulls last
                """
            ),
            {"y": season},
        )
    ).all()
    if not rows:
        return None
    drivers, constructors = [], []
    for r in rows:
        if r.kind == "driver":
            drivers.append(
                DriverStanding(
                    position=r.position,
                    points=r.points,
                    wins=r.wins,
                    driver=DriverRef(
                        id=r.entity_id,
                        code=r.code or r.entity_id[:3].upper(),
                        full_name=r.full_name or r.entity_id,
                        number=r.number,
                        team_id=r.driver_team_id,
                        team_name=r.driver_team_name,
                        color_hex=r.driver_color,
                    ),
                )
            )
        else:
            constructors.append(
                ConstructorStanding(
                    position=r.position,
                    team_id=r.entity_id,
                    team_name=r.team_name or r.entity_id,
                    color_hex=r.team_color,
                    points=r.points,
                    wins=r.wins,
                )
            )
    return StandingsResponse(
        season=season,
        after_round=max(r.after_round for r in rows),
        drivers=drivers,
        constructors=constructors,
    )

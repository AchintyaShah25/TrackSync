"""Race summaries generated from our own data with a fixed template (no LLM), so the chat
agent can cite a short, correct narrative of every race we have."""

from __future__ import annotations

from datetime import datetime

from racemodel.events import periods, race_sequence
from sqlalchemy import Connection, text

from .sources import Document

EVENTS_SQL = text(
    """
    select e.id, e.season, e.round, e.name, e.race_start_utc, c.name as circuit, c.locality
    from events e join circuits c on c.id = e.circuit_id
    where exists (select 1 from results r where r.event_id = e.id and r.session = 'R')
      and (cast(:ids as integer[]) is null or e.id = any(cast(:ids as integer[])))
    order by e.id
    """
)
RESULTS_SQL = text(
    """
    select r.session, r.position, r.grid, r.status, r.time_ms, r.laps, d.id, d.full_name,
           t.name as team
    from results r join drivers d on d.id = r.driver_id
    join events e on e.id = r.event_id
    left join teams t on t.id = r.team_id and t.season = e.season
    where r.event_id = :id and r.session in ('R', 'Q')
    order by r.session, r.position nulls last
    """
)
LAPS_SQL = text(
    "select driver_id, lap, lap_time_ms, track_status from laps "
    "where event_id = :id and session = 'R'"
)
STINTS_SQL = text(
    "select compound, start_lap, end_lap from stints "
    "where event_id = :id and session = 'R' and driver_id = :d order by stint"
)


def _ord(n: int | None) -> str:
    """1 -> "1st", 2 -> "2nd", 11 -> "11th", 22 -> "22nd"; None/0 -> pit lane start."""
    if not n:
        return "the pit lane"
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _lap_time(ms: int) -> str:
    m, s = divmod(ms / 1000, 60)
    return f"{int(m)}:{s:06.3f}"


def _who(r) -> str:
    return f"{r.full_name} ({r.team})" if r.team else r.full_name


def race_summary(conn: Connection, ev) -> Document | None:
    rows = conn.execute(RESULTS_SQL, {"id": ev.id}).all()
    race = [r for r in rows if r.session == "R"]
    quali = [r for r in rows if r.session == "Q"]
    podium = [r for r in race if r.position in (1, 2, 3)]
    if not podium:
        return None
    win = podium[0]
    when = (
        ev.race_start_utc.strftime("%-d %B %Y") if isinstance(ev.race_start_utc, datetime) else ""
    )
    place = f"{ev.circuit}{', ' + ev.locality if ev.locality else ''}"
    lines = [
        f"The {ev.season} {ev.name} was round {ev.round} of the {ev.season} Formula One "
        f"season, held at {place}{' on ' + when if when else ''}."
    ]
    second = next((r for r in podium if r.position == 2), None)
    gap = (
        f", {(second.time_ms - win.time_ms) / 1000:.3f} seconds ahead of {_who(second)}"
        if second and second.time_ms and win.time_ms and second.laps == win.laps
        else (f", ahead of {_who(second)}" if second else "")
    )
    lines.append(f"{_who(win)} won from {_ord(win.grid)} on the grid{gap}.")
    third = next((r for r in podium if r.position == 3), None)
    if third:
        lines.append(f"{_who(third)} finished third.")
    if quali and quali[0].position == 1:
        lines.append(f"{quali[0].full_name} started from pole position.")

    laps = conn.execute(LAPS_SQL, {"id": ev.id}).all()
    timed = [lp for lp in laps if lp.lap_time_ms]
    if timed:
        best = min(timed, key=lambda lp: lp.lap_time_ms)
        name = next((r.full_name for r in race if r.id == best.driver_id), best.driver_id)
        lines.append(
            f"The fastest lap was {_lap_time(best.lap_time_ms)} by {name} on lap {best.lap}."
        )
        neutral = periods(race_sequence([(lp.lap, lp.track_status) for lp in laps]))
        sc = [p for p in neutral if p.kind == "SC"]
        vsc = [p for p in neutral if p.kind == "VSC"]
        if not neutral:
            lines.append("The race had no safety car or virtual safety car periods.")
        else:
            parts = []
            if sc:
                parts.append(
                    f"{len(sc)} safety car period{'s' if len(sc) > 1 else ''} (from lap "
                    + ", ".join(str(p.start) for p in sc)
                    + ")"
                )
            if vsc:
                parts.append(
                    f"{len(vsc)} virtual safety car period{'s' if len(vsc) > 1 else ''} (from lap "
                    + ", ".join(str(p.start) for p in vsc)
                    + ")"
                )
            lines.append("The race had " + " and ".join(parts) + ".")
    stints = conn.execute(STINTS_SQL, {"id": ev.id, "d": win.id}).all()
    if stints:
        stops = len(stints) - 1
        plan = ", then ".join(
            f"{(s.compound or 'unknown').title()} for {s.end_lap - s.start_lap + 1} laps"
            for s in stints
        )
        lines.append(f"The winner made {stops} pit stop{'s' if stops != 1 else ''}: {plan}.")
    retired = [r.full_name for r in race if r.position is None]
    if retired:
        lines.append("Did not finish: " + ", ".join(retired) + ".")
    return Document(
        "summary",
        f"summary:{ev.id}",
        f"{ev.season} {ev.name}: race summary",
        f"/races/{ev.season}/{ev.round}",
        [("Race summary", " ".join(lines))],
        season=ev.season,
        event_id=ev.id,
    )


def race_summaries(conn: Connection, event_ids: list[int] | None = None) -> list[Document]:
    events = conn.execute(EVENTS_SQL, {"ids": event_ids}).all()
    return [d for ev in events if (d := race_summary(conn, ev)) is not None]

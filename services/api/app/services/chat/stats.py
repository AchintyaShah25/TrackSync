"""`query_stats`: the only way the chat agent gets numbers (SPEC M3, decision 0029).

A fixed allow-list of parameterized queries over our own tables. The model picks a query
by name and passes parameters; it never writes SQL. Names like "Monza", "VER" or
"Leclerc" are resolved with lookup queries. Chartable results are registered as datasets
that `make_chart` can reference, so charts can only show real data.
"""

from __future__ import annotations

import statistics
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from racemodel.events import periods, race_sequence
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

MAX_ROWS = 25


class StatsError(Exception):
    """A problem the model should see and can fix (unknown race, ambiguous name...)."""


@dataclass
class Dataset:
    name: str
    kind: str  # "line" (numeric x) or "bar" (category x)
    x_label: str
    y_label: str
    points: list[tuple[Any, float]]


@dataclass
class StatsContext:
    conn: AsyncConnection
    datasets: dict[str, Dataset] = field(default_factory=dict)

    def register(self, ref: str, ds: Dataset) -> str:
        self.datasets[ref] = ds
        return ref


# ---------------------------------------------------------------- name resolution


async def _season(ctx: StatsContext, season: int | None) -> int:
    if season is not None:
        exists = await ctx.conn.scalar(text("select 1 from seasons where year = :y"), {"y": season})
        if not exists:
            raise StatsError(f"no data for season {season}; we cover 2023 onward")
        return season
    latest = await ctx.conn.scalar(
        text(
            "select max(e.season) from events e "
            "where exists (select 1 from results r where r.event_id = e.id and r.session = 'R')"
        )
    )
    if latest is None:
        raise StatsError("no race results loaded yet")
    return latest


async def _event(ctx: StatsContext, season: int | None, race: str | int | None):
    if race is None or str(race).strip() == "":
        raise StatsError("say which race (name, circuit, country or round number)")
    s = await _season(ctx, season)
    raw = str(race).strip()
    if raw.isdigit():
        where, params = "e.round = :n", {"n": int(raw)}
    else:
        where = (
            "(lower(e.name) like :q or lower(c.name) like :q or lower(coalesce(c.locality, '')) "
            "like :q or lower(coalesce(c.country, '')) like :q or e.circuit_id = :exact)"
        )
        params = {"q": f"%{raw.lower()}%", "exact": raw.lower()}
    row = (
        await ctx.conn.execute(
            text(
                f"""
                select e.id, e.season, e.round, e.name, e.race_start_utc, c.name as circuit,
                       c.locality, c.country
                from events e join circuits c on c.id = e.circuit_id
                where e.season = :s and {where}
                order by e.round limit 1
                """
            ),
            {"s": s, **params},
        )
    ).first()
    if row is None:
        raise StatsError(f"no race matching {raw!r} in {s}")
    return row


async def _driver(ctx: StatsContext, who: str | None):
    if not who or not str(who).strip():
        raise StatsError("say which driver")
    q = str(who).strip()
    row = (
        await ctx.conn.execute(
            text(
                """
                select d.id, d.code, d.full_name from drivers d
                where upper(d.code) = upper(:q) or d.id = lower(:q)
                   or lower(d.full_name) like :like
                order by (upper(d.code) = upper(:q)) desc, (d.id = lower(:q)) desc,
                         (select max(r.event_id) from results r where r.driver_id = d.id)
                         desc nulls last
                limit 1
                """
            ),
            {"q": q, "like": f"%{q.lower()}%"},
        )
    ).first()
    if row is None:
        raise StatsError(f"no driver matching {q!r}")
    return row


async def _team(ctx: StatsContext, which: str | None):
    if not which or not str(which).strip():
        raise StatsError("say which team")
    q = str(which).strip().lower()
    row = (
        await ctx.conn.execute(
            text(
                """
                select id, name from teams
                where id = :q or lower(name) like :like
                order by (id = :q) desc, season desc limit 1
                """
            ),
            {"q": q.replace(" ", "_"), "like": f"%{q}%"},
        )
    ).first()
    if row is None:
        raise StatsError(f"no team matching {which!r}")
    return row


def _race_label(ev) -> str:
    return f"{ev.season} {ev.name} (round {ev.round}, {ev.circuit})"


def _secs(ms: int | None) -> float | None:
    return round(ms / 1000, 3) if ms is not None else None


# ---------------------------------------------------------------- queries


async def race_result(ctx: StatsContext, season: int | None = None, race=None, top: int = 10):
    ev = await _event(ctx, season, race)
    rows = (
        await ctx.conn.execute(
            text(
                """
                select r.position, d.code, d.full_name, t.name as team, r.grid, r.points,
                       r.status, r.time_ms, r.laps
                from results r join drivers d on d.id = r.driver_id
                left join teams t on t.id = r.team_id and t.season = :s
                where r.event_id = :e and r.session = 'R'
                order by r.position nulls last, r.laps desc nulls last
                """
            ),
            {"e": ev.id, "s": ev.season},
        )
    ).all()
    if not rows:
        raise StatsError(f"no race result yet for the {_race_label(ev)}")
    win = rows[0]
    fastest = (
        await ctx.conn.execute(
            text(
                """
                select d.full_name, l.lap, l.lap_time_ms
                from laps l join drivers d on d.id = l.driver_id
                where l.event_id = :e and l.session = 'R' and l.lap_time_ms is not null
                order by l.lap_time_ms limit 1
                """
            ),
            {"e": ev.id},
        )
    ).first()
    out = []
    for r in rows[: min(max(top, 1), 20)]:
        if r is win or r.position is None:
            gap = None if r.position else r.status
        elif r.laps is not None and win.laps is not None and r.laps < win.laps:
            gap = f"+{win.laps - r.laps} lap{'s' if win.laps - r.laps > 1 else ''}"
        elif r.time_ms and win.time_ms:
            gap = f"+{(r.time_ms - win.time_ms) / 1000:.3f}s"
        else:
            gap = r.status
        out.append(
            {
                "pos": r.position,
                "driver": r.full_name,
                "code": r.code,
                "team": r.team,
                "grid": r.grid,
                "points": r.points,
                "gap": gap,
            }
        )
    ref = ctx.register(
        f"race_points:{ev.id}",
        Dataset(
            f"Points, {ev.season} {ev.name}",
            "bar",
            "Driver",
            "Points",
            [(r["code"], float(r["points"])) for r in out if r["points"]],
        ),
    )
    return {
        "race": _race_label(ev),
        "date": ev.race_start_utc.date().isoformat() if ev.race_start_utc else None,
        "classification": out,
        "fastest_lap": {
            "driver": fastest.full_name,
            "lap": fastest.lap,
            "time_s": _secs(fastest.lap_time_ms),
        }
        if fastest
        else None,
        "chartable": [ref],
    }


async def qualifying_result(ctx: StatsContext, season: int | None = None, race=None, top: int = 10):
    ev = await _event(ctx, season, race)
    rows = (
        await ctx.conn.execute(
            text(
                """
                select r.position, d.full_name, d.code, t.name as team, r.time_ms
                from results r join drivers d on d.id = r.driver_id
                left join teams t on t.id = r.team_id and t.season = :s
                where r.event_id = :e and r.session = 'Q'
                order by r.position nulls last limit :n
                """
            ),
            {"e": ev.id, "s": ev.season, "n": min(max(top, 1), 20)},
        )
    ).all()
    if not rows:
        raise StatsError(f"no qualifying result for the {_race_label(ev)}")
    return {
        "race": _race_label(ev),
        "qualifying": [
            {
                "pos": r.position,
                "driver": r.full_name,
                "code": r.code,
                "team": r.team,
                "best_lap_s": _secs(r.time_ms),
            }
            for r in rows
        ],
    }


async def driver_season(ctx: StatsContext, season: int | None = None, driver=None):
    s = await _season(ctx, season)
    d = await _driver(ctx, driver)
    rows = (
        await ctx.conn.execute(
            text(
                """
                select e.round, e.name, r.position, r.grid, r.points, r.status, t.name as team
                from results r join events e on e.id = r.event_id
                left join teams t on t.id = r.team_id and t.season = e.season
                where e.season = :s and r.driver_id = :d and r.session = 'R'
                order by e.round
                """
            ),
            {"s": s, "d": d.id},
        )
    ).all()
    if not rows:
        raise StatsError(f"{d.full_name} has no race results in {s}")
    sprint_pts = await ctx.conn.scalar(
        text(
            "select coalesce(sum(r.points), 0) from results r join events e on e.id = r.event_id "
            "where e.season = :s and r.driver_id = :d and r.session = 'S'"
        ),
        {"s": s, "d": d.id},
    )
    finishes = [r.position for r in rows if r.position]
    cumulative, total = [], 0.0
    for r in rows:
        total += r.points
        cumulative.append((r.round, total))
    refs = [
        ctx.register(
            f"finish:{s}:{d.code}",
            Dataset(
                f"{d.code} finishing position {s}",
                "line",
                "Round",
                "Position",
                [(r.round, float(r.position)) for r in rows if r.position],
            ),
        ),
        ctx.register(
            f"points:{s}:{d.code}",
            Dataset(f"{d.code} cumulative race points {s}", "line", "Round", "Points", cumulative),
        ),
    ]
    return {
        "driver": d.full_name,
        "season": s,
        "team": rows[-1].team,
        "races": [
            {
                "round": r.round,
                "race": r.name,
                "pos": r.position,
                "grid": r.grid,
                "points": r.points,
                "status": None if r.position else r.status,
            }
            for r in rows
        ],
        "totals": {
            "race_points": total,
            "sprint_points": float(sprint_pts or 0),
            "wins": finishes.count(1),
            "podiums": sum(1 for p in finishes if p <= 3),
            "average_finish": round(statistics.mean(finishes), 2) if finishes else None,
            "dnfs": sum(1 for r in rows if r.position is None),
        },
        "chartable": refs,
    }


async def standings(
    ctx: StatsContext, season: int | None = None, kind: str = "driver", top: int = 10
):
    s = await _season(ctx, season)
    k = "constructor" if str(kind).lower().startswith(("constructor", "team")) else "driver"
    rows = (
        await ctx.conn.execute(
            text(
                """
                select st.position, st.points, st.wins, st.after_round,
                       coalesce(d.full_name, t.name, st.entity_id) as name, d.code
                from standings st
                left join drivers d on st.kind = 'driver' and d.id = st.entity_id
                left join teams t on st.kind = 'constructor' and t.id = st.entity_id
                     and t.season = st.season
                where st.season = :s and st.kind = :k
                order by st.position nulls last limit :n
                """
            ),
            {"s": s, "k": k, "n": min(max(top, 1), MAX_ROWS)},
        )
    ).all()
    if not rows:
        raise StatsError(f"no {k} standings for {s}")
    ref = ctx.register(
        f"standings:{s}:{k}",
        Dataset(
            f"{s} {k} standings",
            "bar",
            k.title(),
            "Points",
            [(r.code or r.name, float(r.points)) for r in rows],
        ),
    )
    return {
        "season": s,
        "kind": k,
        "after_round": rows[0].after_round,
        "standings": [
            {"pos": r.position, "name": r.name, "points": r.points, "wins": r.wins} for r in rows
        ],
        "chartable": [ref],
    }


async def head_to_head(ctx: StatsContext, season: int | None = None, driver_a=None, driver_b=None):
    s = await _season(ctx, season)
    a, b = await _driver(ctx, driver_a), await _driver(ctx, driver_b)
    if a.id == b.id:
        raise StatsError("pick two different drivers")
    rows = (
        await ctx.conn.execute(
            text(
                """
                select e.round, r.session, r.driver_id, r.position, r.points
                from results r join events e on e.id = r.event_id
                where e.season = :s and r.session in ('R', 'Q') and r.driver_id in (:a, :b)
                order by e.round
                """
            ),
            {"s": s, "a": a.id, "b": b.id},
        )
    ).all()
    by = {}
    for r in rows:
        by.setdefault((r.round, r.session), {})[r.driver_id] = r
    race_ahead = {a.code: 0, b.code: 0}
    quali_ahead = {a.code: 0, b.code: 0}
    points = {a.code: 0.0, b.code: 0.0}
    series = {a.code: [], b.code: []}
    for (rnd, sess), pair in sorted(by.items()):
        for d in (a, b):
            if sess == "R" and d.id in pair:
                points[d.code] += pair[d.id].points
                if pair[d.id].position:
                    series[d.code].append((rnd, float(pair[d.id].position)))
        if a.id in pair and b.id in pair:
            pa, pb = pair[a.id].position, pair[b.id].position
            if pa or pb:
                winner = a.code if (pa and (not pb or pa < pb)) else b.code
                (race_ahead if sess == "R" else quali_ahead)[winner] += 1
    if not any(race_ahead.values()) and not any(quali_ahead.values()):
        raise StatsError(f"{a.full_name} and {b.full_name} did not race each other in {s}")
    refs = [
        ctx.register(
            f"finish:{s}:{d.code}",
            Dataset(
                f"{d.code} finishing position {s}", "line", "Round", "Position", series[d.code]
            ),
        )
        for d in (a, b)
    ]
    return {
        "season": s,
        "drivers": [a.full_name, b.full_name],
        "races_finished_ahead": race_ahead,
        "qualified_ahead": quali_ahead,
        "race_points": points,
        "chartable": refs,
    }


async def race_strategy(ctx: StatsContext, season: int | None = None, race=None, driver=None):
    ev = await _event(ctx, season, race)
    d = await _driver(ctx, driver) if driver else None
    rows = (
        await ctx.conn.execute(
            text(
                """
                select dr.full_name, dr.code, s.stint, s.compound, s.start_lap, s.end_lap,
                       r.position
                from stints s join drivers dr on dr.id = s.driver_id
                left join results r on r.event_id = s.event_id and r.session = 'R'
                     and r.driver_id = s.driver_id
                where s.event_id = :e and s.session = 'R'
                  and (cast(:d as text) is null or s.driver_id = :d)
                order by r.position nulls last, dr.code, s.stint
                """
            ),
            {"e": ev.id, "d": d.id if d else None},
        )
    ).all()
    if not rows:
        raise StatsError(f"no stint data for the {_race_label(ev)}")
    plans: dict[str, dict] = {}
    for r in rows:
        p = plans.setdefault(r.code, {"driver": r.full_name, "finish": r.position, "stints": []})
        p["stints"].append(f"{(r.compound or '?').title()} laps {r.start_lap}-{r.end_lap}")
    out = list(plans.values())[: (1 if d else 10)]
    for p in out:
        p["stops"] = len(p["stints"]) - 1
    return {"race": _race_label(ev), "strategies": out}


async def safety_cars(ctx: StatsContext, season: int | None = None, race=None):
    ev = await _event(ctx, season, race)
    laps = (
        await ctx.conn.execute(
            text("select lap, track_status from laps where event_id = :e and session = 'R'"),
            {"e": ev.id},
        )
    ).all()
    if not laps:
        raise StatsError(f"no lap data for the {_race_label(ev)}")
    found = periods(race_sequence([(r.lap, r.track_status) for r in laps]))
    return {
        "race": _race_label(ev),
        "note": "red flags are counted as safety car periods",
        "periods": [
            {
                "kind": "Safety car" if p.kind == "SC" else "Virtual safety car",
                "from_lap": p.start,
                "laps": p.length,
            }
            for p in found
        ],
    }


async def wins(
    ctx: StatsContext, driver=None, team=None, from_season: int = 2023, to_season: int | None = None
):
    if not driver and not team:
        raise StatsError("give a driver or a team")
    to = await _season(ctx, to_season)
    d = await _driver(ctx, driver) if driver else None
    t = await _team(ctx, team) if team else None
    rows = (
        await ctx.conn.execute(
            text(
                """
                select e.season, e.round, e.name from results r join events e on e.id = r.event_id
                where r.session = 'R' and r.position = 1 and e.season between :f and :t
                  and (cast(:d as text) is null or r.driver_id = :d)
                  and (cast(:team as text) is null or r.team_id = :team)
                order by e.season, e.round
                """
            ),
            {"f": from_season, "t": to, "d": d.id if d else None, "team": t.id if t else None},
        )
    ).all()
    who = d.full_name if d else t.name
    per_season = {s: 0 for s in range(from_season, to + 1)}
    for r in rows:
        per_season[r.season] += 1
    ref = ctx.register(
        f"wins:{who}",
        Dataset(
            f"{who} race wins per season",
            "bar",
            "Season",
            "Wins",
            [(str(s), float(n)) for s, n in per_season.items()],
        ),
    )
    return {
        "who": who,
        "seasons": f"{from_season}-{to}",
        "total_wins": len(rows),
        "wins": [f"{r.season} {r.name}" for r in rows][:MAX_ROWS],
        "chartable": [ref],
    }


async def lap_times(ctx: StatsContext, season: int | None = None, race=None, drivers=None):
    ev = await _event(ctx, season, race)
    names = (
        drivers
        if isinstance(drivers, list)
        else [x for x in str(drivers or "").split(",") if x.strip()]
    )
    if not names or len(names) > 3:
        raise StatsError("give one to three drivers")
    out, refs = [], []
    for name in names:
        d = await _driver(ctx, name)
        rows = (
            await ctx.conn.execute(
                text(
                    """
                    select lap, lap_time_ms, compound, track_status, pit_in, pit_out from laps
                    where event_id = :e and session = 'R' and driver_id = :d
                      and lap_time_ms is not null
                    order by lap
                    """
                ),
                {"e": ev.id, "d": d.id},
            )
        ).all()
        if not rows:
            raise StatsError(f"no laps for {d.full_name} in the {_race_label(ev)}")
        green = [
            r
            for r in rows
            if (r.track_status or "1") == "1" and not r.pit_in and not r.pit_out and r.lap > 1
        ]
        best = min(rows, key=lambda r: r.lap_time_ms)
        out.append(
            {
                "driver": d.full_name,
                "laps": len(rows),
                "fastest_lap": {"lap": best.lap, "time_s": _secs(best.lap_time_ms)},
                "median_green_lap_s": _secs(int(statistics.median(r.lap_time_ms for r in green)))
                if green
                else None,
            }
        )
        refs.append(
            ctx.register(
                f"laps:{ev.id}:{d.code}",
                Dataset(
                    f"{d.code} lap times, {ev.season} {ev.name}",
                    "line",
                    "Lap",
                    "Lap time (s)",
                    [(r.lap, r.lap_time_ms / 1000) for r in green],
                ),
            )
        )
    return {
        "race": _race_label(ev),
        "drivers": out,
        "note": "chart series exclude pit and SC laps",
        "chartable": refs,
    }


async def next_race(ctx: StatsContext):
    now = datetime.now(UTC)
    rows = (
        await ctx.conn.execute(
            text(
                """
                (select e.season, e.round, e.name, e.race_start_utc, c.name as circuit,
                        'next' as which
                 from events e join circuits c on c.id = e.circuit_id
                 where e.race_start_utc > :now order by e.race_start_utc limit 1)
                union all
                (select e.season, e.round, e.name, e.race_start_utc, c.name, 'last'
                 from events e join circuits c on c.id = e.circuit_id
                 where e.race_start_utc <= :now order by e.race_start_utc desc limit 1)
                """
            ),
            {"now": now},
        )
    ).all()
    return {
        r.which: {
            "race": f"{r.season} {r.name}",
            "round": r.round,
            "circuit": r.circuit,
            "start_utc": r.race_start_utc.isoformat() if r.race_start_utc else None,
        }
        for r in rows
    }


Query = Callable[..., Awaitable[dict]]
QUERIES: dict[str, tuple[Query, str]] = {
    "race_result": (
        race_result,
        "Race classification, gaps, points and fastest lap. params: season?, race, top?",
    ),
    "qualifying_result": (
        qualifying_result,
        "Qualifying order and best laps. params: season?, race, top?",
    ),
    "driver_season": (
        driver_season,
        "A driver's results in every race of a season and totals. params: season?, driver",
    ),
    "standings": (
        standings,
        "Championship standings. params: season?, kind ('driver'|'constructor'), top?",
    ),
    "head_to_head": (
        head_to_head,
        "Two drivers compared over a season. params: season?, driver_a, driver_b",
    ),
    "race_strategy": (
        race_strategy,
        "Tyre stints and stops in a race. params: season?, race, driver?",
    ),
    "safety_cars": (safety_cars, "Safety car and VSC periods in a race. params: season?, race"),
    "wins": (
        wins,
        "Race wins for a driver or team. params: driver? | team?, from_season?, to_season?",
    ),
    "lap_times": (
        lap_times,
        "Lap times for 1-3 drivers in a race. params: season?, race, drivers (list)",
    ),
    "next_race": (next_race, "The next and the most recent race. params: none"),
}


async def run_query(ctx: StatsContext, name: str, params: dict[str, Any] | None) -> dict:
    if name not in QUERIES:
        raise StatsError(f"unknown query {name!r}; choose one of {sorted(QUERIES)}")
    fn, _ = QUERIES[name]
    allowed = set(fn.__code__.co_varnames[1 : fn.__code__.co_argcount])
    clean = {k: v for k, v in (params or {}).items() if k in allowed and v not in (None, "")}
    for key in ("season", "from_season", "to_season", "top"):
        if key in clean:
            try:
                clean[key] = int(clean[key])
            except (TypeError, ValueError) as err:
                raise StatsError(f"{key} must be a number") from err
    return await fn(ctx, **clean)

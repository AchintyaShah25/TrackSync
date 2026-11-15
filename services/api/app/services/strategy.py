"""Strategy forecaster: load a past race, estimate the driver's pace, simulate (decision 0021)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from racemodel import MODEL_VERSION, CircuitParams, Stint, simulate, validate_strategy
from racemodel.dataset import RaceLap, racing_laps, wet_events
from racemodel.events import periods, race_sequence
from racemodel.fit import deg_curve, driver_intercept
from racemodel.simulate import SC_I, VSC_I
from racemodel.types import COMPOUND_INDEX, DRY_COMPOUNDS
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from ..schemas.strategy import (
    ActualOut,
    DegCurve,
    GapBands,
    ModelInfo,
    ModelSummary,
    Percentiles,
    PositionProb,
    SimulateRequest,
    SimulateResponse,
    StintIn,
    StrategyOut,
)
from .common import event_drivers

MIN_PACE_LAPS = 5
MAX_LAPPED = 3  # a driver lapped by more than this is treated as not having finished
CURVE_MAX_AGE = 45


class StrategyError(Exception):
    def __init__(self, status: int, detail: str | list[str]):
        super().__init__(detail)
        self.status = status
        self.detail = detail


@dataclass
class RaceData:
    circuit_id: str
    total_laps: int
    laps: list[RaceLap]


async def _race(conn: AsyncConnection, event_id: int) -> RaceData:
    event = (
        await conn.execute(text("select circuit_id from events where id = :id"), {"id": event_id})
    ).first()
    if event is None:
        raise StrategyError(404, f"event {event_id} not found")
    rows = await conn.execute(
        text(
            """
            select driver_id, lap, lap_time_ms, compound, tyre_life, pit_in, pit_out,
                   track_status, is_accurate, deleted
            from laps where event_id = :id and session = 'R'
            order by driver_id, lap
            """
        ),
        {"id": event_id},
    )
    laps = [
        RaceLap(
            event_id=event_id,
            circuit_id=event.circuit_id,
            driver_id=r.driver_id,
            lap=r.lap,
            time=r.lap_time_ms / 1000.0 if r.lap_time_ms is not None else None,
            compound=r.compound,
            tyre_life=r.tyre_life,
            pit_in=r.pit_in,
            pit_out=r.pit_out,
            status=r.track_status,
            is_accurate=r.is_accurate,
            deleted=r.deleted,
        )
        for r in rows
    ]
    if not laps:
        raise StrategyError(422, "this race has no lap data yet; forecasts cover past races")
    if wet_events(laps):
        raise StrategyError(422, "forecasts cover dry races only; this race was wet")
    return RaceData(event.circuit_id, max(r.lap for r in laps), laps)


async def _params(conn: AsyncConnection, circuit_id: str) -> tuple[CircuitParams, dict, int]:
    row = (
        await conn.execute(
            text(
                """
                select params, metrics, n_races, n_laps, fitted_at from circuit_model_params
                where circuit_id = :c and model_version = :v
                """
            ),
            {"c": circuit_id, "v": MODEL_VERSION},
        )
    ).first()
    if row is None:
        raise StrategyError(422, f"the race model is not fitted for {circuit_id} yet")
    return CircuitParams.from_dict(row.params), dict(row._mapping), row.n_races


async def _actual(conn: AsyncConnection, event_id: int, driver_id: str, total_laps: int):
    stints = (
        await conn.execute(
            text(
                """
                select compound, start_lap, end_lap from stints
                where event_id = :e and session = 'R' and driver_id = :d order by stint
                """
            ),
            {"e": event_id, "d": driver_id},
        )
    ).all()
    results = (
        await conn.execute(
            text(
                "select driver_id, position, time_ms, laps from results "
                "where event_id = :e and session = 'R'"
            ),
            {"e": event_id},
        )
    ).all()
    mine = next((r for r in results if r.driver_id == driver_id), None)
    if mine is None or mine.laps is None or mine.laps < total_laps - MAX_LAPPED:
        raise StrategyError(422, "pick a driver who finished this race")
    if not stints or any(s.compound not in COMPOUND_INDEX for s in stints):
        raise StrategyError(422, "this driver's real strategy is incomplete or used wet tyres")
    actual = [Stint(s.compound, s.end_lap - s.start_lap + 1) for s in stints]
    covered = sum(s.laps for s in actual)
    if abs(covered - total_laps) > MAX_LAPPED:
        raise StrategyError(422, "this driver's real strategy is incomplete")
    # Lapped finishers ran fewer laps: extend the final stint to race distance.
    last = actual[-1]
    actual[-1] = Stint(last.compound, last.laps + total_laps - covered)
    if actual[-1].laps < 1:
        raise StrategyError(422, "this driver's real strategy is incomplete")
    others = sorted(
        r.time_ms / 1000.0
        for r in results
        if r.driver_id != driver_id and r.laps == total_laps and r.time_ms is not None
    )
    on_lead_lap = mine.laps == total_laps and mine.time_ms is not None
    return actual, mine, (np.array(others) if on_lead_lap else None)


_FINISH_Q = (5, 25, 50, 75, 95)
_GAP_Q = (10, 25, 50, 75, 90)


def _named(qs: tuple[int, ...], values: np.ndarray) -> dict[str, float]:
    return {f"p{q}": round(float(v), 3) for q, v in zip(qs, np.percentile(values, qs), strict=True)}


def _stints_out(stints: list[Stint]) -> list[StintIn]:
    return [StintIn(compound=s.compound, laps=s.laps) for s in stints]  # type: ignore[arg-type]


def _stop_laps(stints: list[Stint]) -> list[int]:
    return [int(x) for x in np.cumsum([s.laps for s in stints])[:-1]]


async def simulate_strategies(conn: AsyncConnection, req: SimulateRequest) -> SimulateResponse:
    race = await _race(conn, req.event_id)
    drivers = await event_drivers(conn, req.event_id)
    if req.driver_id not in drivers:
        raise StrategyError(422, f"driver {req.driver_id} did not take part in this race")
    strategies = [[Stint(s.compound, s.laps) for s in st.stints] for st in req.strategies]
    problems = [
        f"{st.label}: {err}"
        for st, stints in zip(req.strategies, strategies, strict=True)
        for err in validate_strategy(stints, race.total_laps)
    ]
    if problems:
        raise StrategyError(422, problems)

    params, _, n_races = await _params(conn, race.circuit_id)
    actual, result, others = await _actual(conn, req.event_id, req.driver_id, race.total_laps)
    pace_laps = racing_laps([r for r in race.laps if r.driver_id == req.driver_id])
    if len(pace_laps) < MIN_PACE_LAPS:
        raise StrategyError(422, "not enough clean laps to estimate this driver's pace")
    intercept = driver_intercept(
        params.pace,
        np.array([COMPOUND_INDEX[r.compound] for r in pace_laps]),  # type: ignore[index]
        np.array([r.tyre_life for r in pace_laps], dtype=float),
        np.array([r.lap for r in pace_laps], dtype=float),
        np.array([r.time for r in pace_laps], dtype=float),
    )
    fixed = (
        periods(race_sequence([(r.lap, r.status) for r in race.laps]))
        if req.safety_cars == "actual"
        else None
    )
    sim = simulate(
        params,
        race.total_laps,
        intercept,
        [actual, *strategies],
        runs=req.runs,
        seed=req.seed,
        fixed_periods=fixed,
        validate=False,  # user strategies were validated above; the real one may break rules
    )

    ref = sim.cum[0]
    actual_time = result.time_ms / 1000.0 if others is not None else None
    model_position = int(1 + np.searchsorted(others, actual_time)) if others is not None else None
    out = []
    for st, stints, cum in zip(req.strategies, strategies, sim.cum[1:], strict=True):
        delta = cum - ref
        bands = np.round(np.percentile(delta, _GAP_Q, axis=0), 2)
        positions = p_gain = p_lose = None
        if others is not None:
            finish = actual_time + delta[:, -1]
            pos = 1 + np.searchsorted(others, finish)
            values, counts = np.unique(pos, return_counts=True)
            positions = [
                PositionProb(position=int(v), p=round(c / req.runs, 4))
                for v, c in zip(values, counts, strict=True)
            ]
            p_gain = round(float(np.mean(pos < model_position)), 4)
            p_lose = round(float(np.mean(pos > model_position)), 4)
        out.append(
            StrategyOut(
                label=st.label,
                stints=st.stints,
                stop_laps=_stop_laps(stints),
                finish_delta_s=Percentiles(**_named(_FINISH_Q, delta[:, -1])),
                gap=GapBands(**{f"p{q}": b.tolist() for q, b in zip(_GAP_Q, bands, strict=True)}),
                positions=positions,
                p_gain=p_gain,
                p_lose=p_lose,
            )
        )
    ev = params.events
    return SimulateResponse(
        event_id=req.event_id,
        driver=drivers[req.driver_id],
        total_laps=race.total_laps,
        runs=req.runs,
        seed=req.seed,
        safety_cars=req.safety_cars,
        actual=ActualOut(
            stints=_stints_out(actual),
            stop_laps=_stop_laps(actual),
            position=result.position,
            model_position=model_position,
            race_time_s=actual_time,
        ),
        strategies=out,
        sc_share=np.round(np.mean(sim.neutral == SC_I, axis=0), 3).tolist(),
        vsc_share=np.round(np.mean(sim.neutral == VSC_I, axis=0), 3).tolist(),
        model=ModelInfo(
            version=MODEL_VERSION,
            n_races=n_races,
            sigma=round(params.pace.sigma, 3),
            pit_loss=round(ev.pit_loss, 2),
            sc_rate=ev.sc_rate,
            vsc_rate=ev.vsc_rate,
        ),
    )


async def model_summary(conn: AsyncConnection, circuit_id: str) -> ModelSummary:
    params, meta, n_races = await _params(conn, circuit_id)
    pace, ev = params.pace, params.events
    curves = []
    for c, name in enumerate(DRY_COMPOUNDS):
        top = min(max(pace.age_max[c], 10) + 5, CURVE_MAX_AGE)
        ages = np.arange(1, top + 1, dtype=float)
        curves.append(
            DegCurve(
                compound=name,  # type: ignore[arg-type]
                offset=round(pace.offset[c], 3),
                age=[int(a) for a in ages],
                seconds=np.round(deg_curve(pace, c, ages), 3).tolist(),
            )
        )
    return ModelSummary(
        circuit_id=circuit_id,
        version=MODEL_VERSION,
        n_races=n_races,
        n_laps=meta["n_laps"],
        fitted_at=meta["fitted_at"],
        sigma=round(pace.sigma, 3),
        trend=round(pace.trend, 4),
        pit_loss=round(ev.pit_loss, 2),
        pit_loss_sd=round(ev.pit_loss_sd, 2),
        sc_rate=ev.sc_rate,
        vsc_rate=ev.vsc_rate,
        curves=curves,
    )

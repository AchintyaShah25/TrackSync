"""From raw race laps to fitted CircuitParams (decision 0020).

Shared by the ETL (fit and store), the backtest (fit with a race held out) and the API
(the same clean-lap filter for a driver's pace), so all three agree on what a clean lap is.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np

from .events import GREEN, LapRow, RaceSummary, fit_events, lap_kind, periods, race_sequence
from .events import stop_losses as _stop_losses
from .fit import GROSS_SLOW, PRIOR_LAPS, LapSet, deg_curve, fit_pace
from .types import COMPOUND_INDEX, CircuitParams

WET_COMPOUNDS = frozenset({"INTERMEDIATE", "WET"})
WET_RACE_SHARE = 0.10  # a race with more than 10% of laps on wet tyres is "wet"
DEG_CV_AGE = 15.0  # compare races by tyre wear after this many laps
DEG_CV_MIN_LAPS = 300  # a race needs this many clean laps to estimate its own wear
DEG_CV_BOUNDS = (0.1, 0.6)
DEG_CV_DEFAULT = 0.3


@dataclass(frozen=True)
class RaceLap:
    event_id: int
    circuit_id: str
    driver_id: str
    lap: int
    time: float | None  # seconds
    compound: str | None
    tyre_life: int | None
    pit_in: bool
    pit_out: bool
    status: str | None
    is_accurate: bool = True
    deleted: bool = False


@dataclass
class CircuitFit:
    params: CircuitParams
    metrics: dict
    n_races: int  # dry races used for the pace fit
    n_laps: int


def is_clean(r: RaceLap) -> bool:
    """A green, accurate, dry racing lap: usable for fitting pace."""
    return (
        r.lap > 1
        and r.time is not None
        and r.tyre_life is not None
        and not r.pit_in
        and not r.pit_out
        and r.is_accurate
        and not r.deleted
        and r.compound in COMPOUND_INDEX
        and lap_kind(r.status) == GREEN
    )


def racing_laps(laps: list[RaceLap]) -> list[RaceLap]:
    """One driver's clean laps in one race, minus gross outliers (> 107% of their median).

    Catches what track status misses: unflagged SC laps (Spa 2025 started behind the SC
    without the laps being marked), damage, or a driver backing up the field. The fit
    applies the same rule; the API and the backtest use this before estimating pace.
    """
    clean = [r for r in laps if is_clean(r)]
    if not clean:
        return []
    med = float(np.median([r.time for r in clean]))
    return [r for r in clean if r.time <= GROSS_SLOW * med]  # type: ignore[operator]


def wet_events(rows: Iterable[RaceLap]) -> set[int]:
    total: dict[int, int] = defaultdict(int)
    wet: dict[int, int] = defaultdict(int)
    for r in rows:
        total[r.event_id] += 1
        wet[r.event_id] += r.compound in WET_COMPOUNDS
    return {e for e, n in total.items() if wet[e] > WET_RACE_SHARE * n}


def lap_set(rows: Iterable[RaceLap]) -> LapSet:
    return LapSet.from_rows(
        [((r.event_id, r.driver_id), r.compound, r.tyre_life, r.lap, r.time) for r in rows]  # type: ignore[misc]
    )


def race_summaries(rows: list[RaceLap]) -> list[RaceSummary]:
    by_event: dict[int, list[RaceLap]] = defaultdict(list)
    for r in rows:
        by_event[r.event_id].append(r)
    out = []
    for laps in by_event.values():
        by_driver: dict[str, list[LapRow]] = defaultdict(list)
        for r in laps:
            by_driver[r.driver_id].append(
                LapRow(r.lap, r.time, r.compound, r.pit_in, r.pit_out, r.status)
            )
        losses = [
            x for d in by_driver.values() for x in _stop_losses(sorted(d, key=lambda z: z.lap))
        ]
        seq = race_sequence([(r.lap, r.status) for r in laps])
        out.append(
            RaceSummary(
                circuit_id=laps[0].circuit_id,
                total_laps=max(r.lap for r in laps),
                periods=periods(seq),
                pit_losses=losses,
            )
        )
    return out


def race_wear_spread(by_circuit: dict[str, list[RaceLap]], circuit_pace: dict) -> float:
    """Log-scale sd of each dry race's tyre wear relative to its circuit's fit.

    Each race is fitted on its own (lightly anchored to its circuit), and its wear after
    DEG_CV_AGE laps is compared with the circuit's, per compound it used. A robust sd of
    the log ratios across races is the simulator's per-run wear uncertainty.
    """
    logs = []
    age = np.array([DEG_CV_AGE])
    for cid, laps in by_circuit.items():
        by_event: dict[int, list[RaceLap]] = defaultdict(list)
        for r in laps:
            by_event[r.event_id].append(r)
        base = circuit_pace[cid]
        for race in by_event.values():
            if len(race) < DEG_CV_MIN_LAPS:
                continue
            own, _ = fit_pace(lap_set(race), prior=np.array(base.coef_vector()), prior_laps=50.0)
            used = {COMPOUND_INDEX[r.compound] for r in race}  # type: ignore[index]
            mine = sum(float(deg_curve(own, c, age)[0]) for c in used)
            ref = sum(float(deg_curve(base, c, age)[0]) for c in used)
            if mine > 0.05 and ref > 0.05:
                logs.append(np.log(mine / ref))
    if len(logs) < 5:
        return DEG_CV_DEFAULT
    arr = np.array(logs)
    sd = 1.4826 * float(np.median(np.abs(arr - np.median(arr))))
    return round(min(max(sd, DEG_CV_BOUNDS[0]), DEG_CV_BOUNDS[1]), 3)


def fit_circuits(
    rows: list[RaceLap],
    exclude_events: frozenset[int] = frozenset(),
    prior_laps: float = PRIOR_LAPS,
) -> dict[str, CircuitFit]:
    """Fit every circuit present in `rows`, leaving out `exclude_events` entirely."""
    rows = [r for r in rows if r.event_id not in exclude_events]
    if not rows:
        return {}
    wet = wet_events(rows)
    clean = [r for r in rows if r.event_id not in wet and is_clean(r)]
    global_pace, _ = fit_pace(lap_set(clean))
    prior = np.array(global_pace.coef_vector())
    events = fit_events(race_summaries(rows))

    by_circuit: dict[str, list[RaceLap]] = defaultdict(list)
    for r in clean:
        by_circuit[r.circuit_id].append(r)
    circuit_pace = {
        cid: fit_pace(lap_set(laps), prior=prior, prior_laps=prior_laps)
        for cid, laps in by_circuit.items()
    }
    deg_cv = race_wear_spread(by_circuit, {c: p for c, (p, _) in circuit_pace.items()})

    out = {}
    for cid in sorted({r.circuit_id for r in rows}):
        laps = by_circuit.get(cid, [])
        if cid in circuit_pace:
            pace, metrics = circuit_pace[cid]
        else:
            pace, metrics = fit_pace(lap_set(laps), prior=prior, prior_laps=prior_laps)
        pace.deg_cv = deg_cv
        metrics = {**metrics, "deg_cv": deg_cv}
        n_races = len({r.event_id for r in laps})
        metrics = {**metrics, "n_races": n_races, "prior_laps": prior_laps}
        out[cid] = CircuitFit(
            params=CircuitParams(cid, pace, events[cid]),
            metrics=metrics,
            n_races=n_races,
            n_laps=metrics["n_laps"],
        )
    return out

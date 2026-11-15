"""Vectorized Monte Carlo race simulation (decision 0021).

Every strategy in one call shares the same random race: the same safety cars, pace noise
and pit-crew draws (common random numbers). Differences between strategies then come from
tyres and pit timing, not from luck in the random draws.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .events import SC, VSC, Period
from .fit import deg_curve
from .types import COMPOUND_INDEX, MAX_STINTS, CircuitParams, Stint, validate_strategy

DEFAULT_RUNS = 500
GREEN_I, SC_I, VSC_I = 0, 1, 2
MIN_PIT_SHARE = 0.7  # a stop is never faster than 70% of the typical loss


@dataclass
class SimResult:
    cum: np.ndarray  # (strategies, runs, laps) cumulative race time in seconds
    neutral: np.ndarray  # (runs, laps) 0 green, 1 SC, 2 VSC
    stop_laps: list[list[int]]  # per strategy, laps (1-based) ending with a pit stop


def _neutralizations(
    rng: np.random.Generator, params: CircuitParams, runs: int, laps: int
) -> np.ndarray:
    ev = params.events
    status = np.zeros((runs, laps), dtype=np.int8)
    fractions = np.asarray(ev.start_fractions, dtype=np.float64)
    lap_idx = np.arange(laps)
    # VSC first so an overlapping SC wins.
    for code, rate, durations in (
        (VSC_I, ev.vsc_rate, ev.vsc_durations),
        (SC_I, ev.sc_rate, ev.sc_durations),
    ):
        counts = rng.poisson(rate, runs)
        durs = np.asarray(durations, dtype=np.int64)
        for k in range(int(counts.max(initial=0))):
            active = counts > k
            start = np.clip(np.rint(rng.choice(fractions, runs) * laps), 1, laps - 2).astype(int)
            length = rng.choice(durs, runs)
            mask = (lap_idx >= start[:, None]) & (lap_idx < (start + length)[:, None])
            status[mask & active[:, None]] = code
    return status


def fixed_status(fixed: list[Period], runs: int, laps: int) -> np.ndarray:
    status = np.zeros((runs, laps), dtype=np.int8)
    for p in fixed:
        code = SC_I if p.kind == SC else VSC_I if p.kind == VSC else GREEN_I
        status[:, max(p.start - 1, 0) : min(p.start - 1 + p.length, laps)] = code
    return status


def _tyre_plan(stints: list[Stint]) -> tuple[np.ndarray, np.ndarray, list[int]]:
    compound, age, stops = [], [], []
    lap = 0
    for i, s in enumerate(stints):
        compound += [COMPOUND_INDEX[s.compound]] * s.laps
        age += list(range(1, s.laps + 1))
        lap += s.laps
        if i < len(stints) - 1:
            stops.append(lap)
    return np.array(compound), np.array(age, dtype=np.float64), stops


def simulate(
    params: CircuitParams,
    total_laps: int,
    intercept: float,
    strategies: list[list[Stint]],
    runs: int = DEFAULT_RUNS,
    seed: int = 0,
    fixed_periods: list[Period] | None = None,
    validate: bool = True,
) -> SimResult:
    """Simulate each strategy `runs` times on the same random races.

    `validate=False` skips the dry-race rules (used for a driver's real strategy, which
    may break them, e.g. a free tyre change under a red flag); lap totals must still match.
    """
    for s in strategies:
        laps = sum(st.laps for st in s)
        if validate:
            errors = validate_strategy(s, total_laps)
        else:
            errors = [f"strategy covers {laps} of {total_laps} laps"] if laps != total_laps else []
        if errors:
            raise ValueError("; ".join(errors))
    rng = np.random.default_rng(seed)
    pace, ev = params.pace, params.events
    laps = total_laps
    lap_no = np.arange(1, laps + 1, dtype=np.float64)

    noise = rng.normal(0.0, pace.sigma, (runs, laps))
    # Independent pit-crew draws per strategy: stop luck is real variance between plans.
    pit_draws = rng.normal(0.0, 1.0, (len(strategies), runs, MAX_STINTS))
    # How hard tyres wear on the day: one mean-1 lognormal factor per run, shared by all
    # strategies, so plans with longer stints carry more wear risk.
    cv = max(pace.deg_cv, 0.0)
    deg_mult = np.exp(rng.normal(-0.5 * cv * cv, cv, runs))[:, None]
    if fixed_periods is None:
        status = _neutralizations(rng, params, runs, laps)
    else:
        status = fixed_status(fixed_periods, runs, laps)

    extra = np.where(status == SC_I, ev.sc_lap_extra, 0.0) + np.where(
        status == VSC_I, ev.vsc_lap_extra, 0.0
    )
    common = intercept + pace.trend * lap_no + noise + extra
    pit_factor = np.where(
        status == SC_I, ev.sc_pit_factor, np.where(status == VSC_I, ev.vsc_pit_factor, 1.0)
    )

    out = np.empty((len(strategies), runs, laps))
    all_stops = []
    for si, stints in enumerate(strategies):
        compound, age, stops = _tyre_plan(stints)
        offset = np.asarray(pace.offset)[compound]
        wear = np.zeros(laps)
        for c in np.unique(compound):
            m = compound == c
            wear[m] = deg_curve(pace, int(c), age[m])
        t = common + offset[None, :] + deg_mult * wear[None, :]
        for j, stop_lap in enumerate(stops):
            loss = np.maximum(
                ev.pit_loss + ev.pit_loss_sd * pit_draws[si, :, j], MIN_PIT_SHARE * ev.pit_loss
            )
            t[:, stop_lap - 1] += loss * pit_factor[:, stop_lap - 1]
        out[si] = np.cumsum(t, axis=1)
        all_stops.append(stops)
    return SimResult(cum=out, neutral=status, stop_laps=all_stops)


def percentiles(values: np.ndarray, qs: tuple[float, ...], axis: int = 0) -> np.ndarray:
    return np.percentile(values, qs, axis=axis)

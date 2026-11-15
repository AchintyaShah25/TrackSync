"""Safety cars, VSCs and pit losses from race history (decision 0021)."""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from .types import COMPOUND_INDEX, EventParams

GREEN, SC, VSC = "G", "SC", "VSC"
PRIOR_RACES = 4.0  # SC/VSC rate shrinkage strength, in races
PRIOR_STOPS = 20.0  # pit-loss shrinkage strength, in stops
MIN_PIT_SD = 1.0


@dataclass(frozen=True)
class Period:
    kind: str  # SC or VSC
    start: int  # first neutralized lap (1-based)
    length: int


@dataclass(frozen=True)
class LapRow:
    lap: int
    time: float | None  # seconds
    compound: str | None
    pit_in: bool
    pit_out: bool
    status: str | None  # FastF1 track status codes seen on the lap, e.g. "1", "24"


@dataclass
class RaceSummary:
    circuit_id: str
    total_laps: int
    periods: list[Period]
    pit_losses: list[float] = field(default_factory=list)


def lap_kind(status: str | None) -> str:
    """4 = SC and 5 = red flag count as SC; 6/7 = VSC (deploy/ending)."""
    s = status or ""
    if "4" in s or "5" in s:
        return SC
    if "6" in s or "7" in s:
        return VSC
    return GREEN


def race_sequence(rows: list[tuple[int, str | None]]) -> list[str]:
    """Majority vote per lap over all drivers' (lap, status) rows -> kind per lap (index lap-1)."""
    by_lap: dict[int, list[str]] = {}
    for lap, status in rows:
        by_lap.setdefault(lap, []).append(lap_kind(status))
    if not by_lap:
        return []
    seq = []
    for lap in range(1, max(by_lap) + 1):
        kinds = by_lap.get(lap, [])
        best = GREEN
        for k in (SC, VSC):
            if kinds and kinds.count(k) * 2 > len(kinds):
                best = k
        seq.append(best)
    return seq


def periods(seq: list[str]) -> list[Period]:
    out: list[Period] = []
    i = 0
    while i < len(seq):
        if seq[i] == GREEN:
            i += 1
            continue
        j = i
        while j < len(seq) and seq[j] == seq[i]:
            j += 1
        out.append(Period(seq[i], i + 1, j - i))
        i = j
    return out


def stop_losses(laps: list[LapRow]) -> list[float]:
    """Seconds lost per green-flag dry stop for one driver-race.

    loss = in-lap + out-lap - 2 x the driver's median clean lap. Stops touching a
    neutralized lap or a wet tyre are skipped.
    """
    clean = [
        r.time
        for r in laps
        if r.time is not None
        and r.lap > 1
        and not r.pit_in
        and not r.pit_out
        and lap_kind(r.status) == GREEN
        and r.compound in COMPOUND_INDEX
    ]
    if len(clean) < 5:
        return []
    ref = statistics.median(clean)
    by_lap = {r.lap: r for r in laps}
    out = []
    for r in laps:
        nxt = by_lap.get(r.lap + 1)
        if not (r.pit_in and nxt and nxt.pit_out):
            continue
        pair = (r, nxt)
        if any(p.time is None or lap_kind(p.status) != GREEN for p in pair):
            continue
        if any(p.compound not in COMPOUND_INDEX for p in pair):
            continue
        loss = r.time + nxt.time - 2 * ref  # type: ignore[operator]
        if 5.0 < loss < 60.0:  # drop drive-throughs, long repairs and timing glitches
            out.append(loss)
    return out


def fit_events(races: list[RaceSummary]) -> dict[str, EventParams]:
    """Per-circuit EventParams, shrunk toward the pooled history."""
    if not races:
        return {}
    n_all = len(races)
    sc_all = sum(p.kind == SC for r in races for p in r.periods)
    vsc_all = sum(p.kind == VSC for r in races for p in r.periods)
    losses_all = [x for r in races for x in r.pit_losses]
    g_loss = statistics.median(losses_all) if losses_all else 22.0
    fractions = [p.start / r.total_laps for r in races for p in r.periods if r.total_laps]
    sc_durs = [p.length for r in races for p in r.periods if p.kind == SC]
    vsc_durs = [p.length for r in races for p in r.periods if p.kind == VSC]

    by_circuit: dict[str, list[RaceSummary]] = {}
    for r in races:
        by_circuit.setdefault(r.circuit_id, []).append(r)

    # Pooled spread of losses around each circuit's own median.
    resid = []
    for rs in by_circuit.values():
        ls = [x for r in rs for x in r.pit_losses]
        if len(ls) >= 3:
            m = statistics.median(ls)
            resid += [abs(x - m) for x in ls]
    pit_sd = max(1.4826 * statistics.median(resid), MIN_PIT_SD) if resid else 2.0

    out = {}
    for cid, rs in by_circuit.items():
        n = len(rs)
        k_sc = sum(p.kind == SC for r in rs for p in r.periods)
        k_vsc = sum(p.kind == VSC for r in rs for p in r.periods)
        ls = [x for r in rs for x in r.pit_losses]
        loss = g_loss
        if ls:
            loss = (len(ls) * statistics.median(ls) + PRIOR_STOPS * g_loss) / (
                len(ls) + PRIOR_STOPS
            )
        out[cid] = EventParams(
            sc_rate=round((k_sc + PRIOR_RACES * sc_all / n_all) / (n + PRIOR_RACES), 4),
            vsc_rate=round((k_vsc + PRIOR_RACES * vsc_all / n_all) / (n + PRIOR_RACES), 4),
            pit_loss=round(loss, 3),
            pit_loss_sd=round(pit_sd, 3),
            start_fractions=[round(f, 4) for f in fractions] or [0.1, 0.3, 0.5, 0.7],
            sc_durations=sc_durs or [3, 4, 5],
            vsc_durations=vsc_durs or [1, 2, 3],
        )
    return out

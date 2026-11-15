from racemodel.dataset import RaceLap, fit_circuits, is_clean, racing_laps, wet_events
from racemodel.synthetic import synthetic_laps
from racemodel.types import DRY_COMPOUNDS


def _lap(**kw) -> RaceLap:
    base = dict(
        event_id=1, circuit_id="monza", driver_id="d", lap=5, time=90.0, compound="MEDIUM",
        tyre_life=4, pit_in=False, pit_out=False, status="1",
    )  # fmt: skip
    return RaceLap(**{**base, **kw})


def test_is_clean_rejects_each_excluded_kind_of_lap():
    """Lap 1, pit laps, neutralized, inaccurate, deleted, wet and timeless laps are excluded.

    Why: SPEC M2 lists these exclusions; the ETL, backtest and API share this one filter.
    """
    assert is_clean(_lap())
    for bad in (
        _lap(lap=1), _lap(pit_in=True), _lap(pit_out=True), _lap(status="4"),
        _lap(status="6"), _lap(is_accurate=False), _lap(deleted=True),
        _lap(compound="INTERMEDIATE"), _lap(time=None), _lap(tyre_life=None),
    ):  # fmt: skip
        assert not is_clean(bad)


def test_wet_events_flags_races_with_many_wet_laps():
    """A race with more than 10% of laps on intermediates or wets counts as wet.

    Why: wet races distort pace and pit loss; the forecaster covers dry races only.
    """
    dry = [_lap(event_id=1, lap=i) for i in range(2, 50)]
    wet = [
        _lap(event_id=2, lap=i, compound="INTERMEDIATE" if i < 10 else "MEDIUM")
        for i in range(2, 50)
    ]
    assert wet_events(dry + wet) == {2}


def _rows(event_id: int, circuit: str, seed: int) -> list[RaceLap]:
    laps = synthetic_laps(n_groups=6, laps=40, seed=seed)
    return [
        RaceLap(
            event_id, circuit, f"d{int(laps.group[i])}", int(laps.lap[i]), float(laps.time[i]),
            DRY_COMPOUNDS[laps.compound[i]], int(laps.age[i]), False, False, "1",
        )
        for i in range(len(laps))
    ]  # fmt: skip


def test_fit_circuits_holds_out_excluded_events():
    """Excluded events contribute nothing, so a backtest never sees its test race.

    Why: leave-one-race-out evaluation is only honest if the held-out laps are absent.
    """
    rows = _rows(1, "monza", 1) + _rows(2, "monza", 2) + _rows(3, "spa", 3)
    full = fit_circuits(rows)
    held = fit_circuits(rows, exclude_events=frozenset({2}))
    assert full["monza"].n_races == 2 and held["monza"].n_races == 1
    assert held["monza"].n_laps < full["monza"].n_laps
    assert set(full) == {"monza", "spa"}


def test_racing_laps_drops_unflagged_slow_laps():
    """Laps far slower than the driver's median are dropped even when marked green.

    Why: Spa 2025 started behind the safety car without the laps being flagged; those
    laps made the backtest's pace estimate 60 s off. The API's pace estimate uses this too.
    """
    laps = [_lap(lap=i, time=90.0) for i in range(2, 30)]
    laps += [_lap(lap=i, time=150.0) for i in range(30, 33)]  # unflagged SC laps
    kept = racing_laps(laps)
    assert len(kept) == 28 and max(r.time for r in kept) == 90.0

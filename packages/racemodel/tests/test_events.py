import pytest
from racemodel.events import (
    SC,
    VSC,
    LapRow,
    Period,
    RaceSummary,
    fit_events,
    lap_kind,
    periods,
    race_sequence,
    stop_losses,
)


def test_lap_kind_maps_track_status_codes():
    """FastF1 codes map to SC (4, red flag 5), VSC (6, 7) and green.

    Why: neutralized laps must be excluded from fitting and counted as events.
    """
    assert lap_kind("1") == "G"
    assert lap_kind("24") == SC
    assert lap_kind("5") == SC
    assert lap_kind("67") == VSC
    assert lap_kind(None) == "G"


def test_race_sequence_uses_majority_and_periods_merge_runs():
    """A lap is neutralized only if most drivers saw it; consecutive laps form one period.

    Why: one driver's lap can straddle the SC call; the race-level view must not
    double count deployments.
    """
    rows = []
    for d in range(3):
        for lap in range(1, 11):
            status = "4" if 4 <= lap <= 6 else "6" if lap == 9 else "1"
            rows.append((lap, "4" if (d == 0 and lap == 2) else status))
    seq = race_sequence(rows)
    assert seq[1] == "G"  # only 1 of 3 drivers saw SC on lap 2
    assert periods(seq) == [Period(SC, 4, 3), Period(VSC, 9, 1)]


def test_stop_losses_skip_neutralized_and_wet_stops():
    """Pit loss counts green dry stops only, relative to the driver's median clean lap.

    Why: a stop under SC or onto intermediates costs far less or more and would skew
    the median pit loss.
    """
    laps = [LapRow(lap, 90.0, "MEDIUM", False, False, "1") for lap in range(1, 31)]
    laps[9] = LapRow(10, 100.0, "MEDIUM", True, False, "1")  # green stop: 10 + 12 = 22 s
    laps[10] = LapRow(11, 102.0, "HARD", False, True, "1")
    laps[19] = LapRow(20, 95.0, "HARD", True, False, "4")  # under SC: skipped
    laps[20] = LapRow(21, 100.0, "SOFT", False, True, "4")
    assert stop_losses(laps) == [pytest.approx(22.0)]


def test_fit_events_shrinks_rates_toward_pooled_history():
    """A circuit with one SC-free race gets an SC rate between 0 and the pooled rate.

    Why: one race is not evidence that a circuit never has safety cars.
    """
    races = [RaceSummary("a", 50, [Period(SC, 10, 4)], [22.0, 23.0]) for _ in range(9)]
    races.append(RaceSummary("b", 50, [], [30.0]))
    params = fit_events(races)
    pooled = 9 / 10
    assert 0 < params["b"].sc_rate < pooled
    assert params["a"].sc_rate == pytest.approx((9 + 4 * pooled) / (9 + 4), abs=1e-3)
    assert 22.0 < params["b"].pit_loss < 30.0

import copy

import numpy as np
import pytest
from racemodel import CircuitParams, EventParams, Period, Stint, fit_pace, simulate
from racemodel.synthetic import synthetic_laps

LAPS = 50


@pytest.fixture(scope="module")
def params() -> CircuitParams:
    pace, _ = fit_pace(synthetic_laps())
    return CircuitParams(
        "test", pace, EventParams(sc_rate=0.6, vsc_rate=0.4, pit_loss=22.0, pit_loss_sd=2.0)
    )


ONE_STOP = [Stint("MEDIUM", 25), Stint("HARD", 25)]
TWO_STOP = [Stint("SOFT", 15), Stint("MEDIUM", 18), Stint("SOFT", 17)]


def test_shapes_and_seeded_determinism(params):
    """Output is (strategies, runs, laps) cumulative time, identical for the same seed.

    Why: static example pages and API tests rely on reproducible results.
    """
    a = simulate(params, LAPS, 90.0, [ONE_STOP, TWO_STOP], runs=200, seed=7)
    b = simulate(params, LAPS, 90.0, [ONE_STOP, TWO_STOP], runs=200, seed=7)
    assert a.cum.shape == (2, 200, LAPS)
    assert np.array_equal(a.cum, b.cum)
    assert np.all(np.diff(a.cum, axis=2) > 0)  # time always increases
    assert a.stop_laps == [[25], [15, 33]]


def test_pit_stop_costs_roughly_the_pit_loss(params):
    """With no neutralizations, an extra stop costs about pit_loss minus the tyre gain.

    Why: sanity check that stops are added once, on the in-lap.
    """
    params = copy.deepcopy(params)  # module fixture: do not leak the change
    params.events.sc_rate = params.events.vsc_rate = 0.0
    res = simulate(params, LAPS, 90.0, [ONE_STOP], runs=300, seed=1)
    lap_times = np.diff(res.cum[0], axis=1, prepend=0)
    jump = lap_times[:, 24] - lap_times[:, 23]
    assert np.median(jump) == pytest.approx(22.0, abs=1.5)


def test_stopping_under_safety_car_is_cheaper(params):
    """A stop on an SC lap costs less than the same stop under green.

    Why: cheap stops under SC are the main way luck changes strategy outcomes.
    """
    green = simulate(params, LAPS, 90.0, [ONE_STOP], runs=100, seed=3, fixed_periods=[])
    sc = simulate(
        params, LAPS, 90.0, [ONE_STOP], runs=100, seed=3, fixed_periods=[Period("SC", 24, 3)]
    )
    sc_cost = sc.cum[0, :, -1] - green.cum[0, :, -1]
    # 3 SC laps add 3 x sc_lap_extra; the stop on lap 25 gets the SC discount.
    expected = 3 * params.events.sc_lap_extra - 0.5 * 22.0
    assert np.median(sc_cost) == pytest.approx(expected, abs=2.0)


def test_strategies_share_random_races_except_pit_luck(params):
    """Two copies of one strategy match lap for lap until the stop; after it they differ
    by a constant (their independent pit-stop draws), never by lap-time noise.

    Why: common random numbers (shared SCs, noise, tyre wear) make gaps reflect the plan;
    pit-crew luck is the one thing drawn per strategy (decision 0021).
    """
    res = simulate(params, LAPS, 90.0, [ONE_STOP, ONE_STOP], runs=100, seed=5)
    diff = res.cum[0] - res.cum[1]
    assert np.allclose(diff[:, :24], 0.0)  # laps before the stop on lap 25
    assert np.allclose(diff[:, 24:], diff[:, [24]])  # constant after the stop
    assert diff[:, -1].std() > 0.5  # pit luck is real variance


def test_wear_uncertainty_widens_long_stint_outcomes(params):
    """With wear uncertainty on, the finish spread grows; with deg_cv=0 it shrinks.

    Why: a one-stop's risk is tyres falling off; the fan chart must show that risk.
    """
    import copy as _copy

    calm = _copy.deepcopy(params)
    calm.events.sc_rate = calm.events.vsc_rate = 0.0
    calm.events.pit_loss_sd = 0.0
    wild = _copy.deepcopy(calm)
    calm.pace.deg_cv, wild.pace.deg_cv = 0.0, 0.4
    long_stints = [Stint("MEDIUM", 20), Stint("HARD", 30)]
    a = simulate(calm, LAPS, 90.0, [ONE_STOP, long_stints], runs=400, seed=2)
    b = simulate(wild, LAPS, 90.0, [ONE_STOP, long_stints], runs=400, seed=2)
    spread = lambda r: np.std(r.cum[1, :, -1] - r.cum[0, :, -1])  # noqa: E731
    assert spread(a) < 1e-9 and spread(b) > 0.05


def test_invalid_strategy_is_rejected(params):
    """A one-compound or wrong-length strategy raises instead of simulating.

    Why: the dry two-compound rule is enforced (decision with the user, M2 plan).
    """
    with pytest.raises(ValueError, match="two different compounds"):
        simulate(params, LAPS, 90.0, [[Stint("HARD", 25), Stint("HARD", 25)]])
    with pytest.raises(ValueError, match="race is 50 laps"):
        simulate(params, LAPS, 90.0, [[Stint("MEDIUM", 20), Stint("HARD", 20)]])


def test_500_runs_is_fast(params):
    """500 runs x 4 strategies x 70 laps runs well under the 1.5 s API budget.

    Why: SPEC M2 acceptance requires simulate responses under 1.5 s.
    """
    import time

    strategies = [[Stint("MEDIUM", 35), Stint("HARD", 35)]] * 4
    t0 = time.perf_counter()
    simulate(params, 70, 90.0, strategies, runs=500, seed=0)
    assert time.perf_counter() - t0 < 0.5

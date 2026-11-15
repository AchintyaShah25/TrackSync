import numpy as np
from racemodel.fit import (
    LapSet,
    deg_curve,
    driver_intercept,
    fit_pace,
    predict_offsets,
)
from racemodel.synthetic import TRUE_BETA, synthetic_laps


def test_fit_recovers_known_coefficients():
    """On synthetic races, the fit recovers offsets, degradation and trend.

    Why: if the estimator is biased on clean data, every forecast built on it is wrong.
    """
    params, metrics = fit_pace(synthetic_laps())
    beta = np.array(params.coef_vector())
    assert np.allclose(beta[:2], TRUE_BETA[:2], atol=0.08)  # compound offsets
    assert np.allclose(beta[2:5], TRUE_BETA[2:5], atol=0.02)  # linear deg
    assert abs(beta[8] - TRUE_BETA[8]) < 0.01  # lap trend
    assert abs(metrics["sigma"] - 0.3) < 0.05


def test_outliers_do_not_bias_the_fit():
    """Gross slow laps (traffic, a spin) are filtered before they distort coefficients.

    Why: real races contain such laps even after the track-status filters.
    """
    laps = synthetic_laps(seed=2)
    rng = np.random.default_rng(0)
    bad = rng.choice(len(laps), size=len(laps) // 50, replace=False)
    laps.time[bad] += rng.uniform(3, 12, len(bad))
    params, _ = fit_pace(laps)
    assert abs(params.trend - TRUE_BETA[8]) < 0.012
    assert abs(params.offset[2] - TRUE_BETA[1]) < 0.12


def test_sparse_circuit_is_shrunk_toward_prior():
    """A circuit with few laps lands near the global prior; a data-rich one keeps its own fit.

    Why: most circuits have at most 4 races (SPEC M2: shrink sparse circuits).
    """
    prior = TRUE_BETA.copy()
    local_beta = TRUE_BETA.copy()
    local_beta[8] = -0.12  # this circuit's true trend differs from the prior
    sparse = synthetic_laps(n_groups=2, laps=20, seed=3, beta=local_beta)
    rich = synthetic_laps(n_groups=80, seed=4, beta=local_beta)
    p_sparse, _ = fit_pace(sparse, prior=prior)
    p_rich, _ = fit_pace(rich, prior=prior)
    assert abs(p_sparse.trend - prior[8]) < abs(p_sparse.trend - local_beta[8])
    assert abs(p_rich.trend - local_beta[8]) < 0.02


def test_empty_circuit_falls_back_to_prior():
    """No clean laps at a circuit returns the prior coefficients rather than failing.

    Why: a new circuit (or a fully wet history) must still be simulatable.
    """
    empty = LapSet(*(np.array([], dtype=t) for t in (int, int, float, float, float)))
    params, metrics = fit_pace(empty, prior=TRUE_BETA)
    assert np.allclose(params.coef_vector(), TRUE_BETA)
    assert metrics["n_laps"] == 0


def test_deg_curve_never_improves_beyond_observed_ages():
    """Past the oldest observed tyre age, degradation extrapolates linearly and never gets faster.

    Why: a quadratic fitted on 30-lap stints can turn downward at 45 laps and would
    make absurdly long stints look fast.
    """
    params, _ = fit_pace(synthetic_laps())
    params.deg2 = [-0.004, -0.004, -0.004]  # force a downward-bending curve
    params.age_max = [20, 20, 20]
    ages = np.arange(1, 60, dtype=float)
    curve = deg_curve(params, 0, ages)
    assert np.all(np.diff(curve[19:]) >= -1e-12)


def test_driver_intercept_recovers_pace():
    """A driver's intercept equals their pace when laps follow the model exactly.

    Why: the API computes each driver's pace this way before simulating.
    """
    params, _ = fit_pace(synthetic_laps())
    comp = np.array([1] * 20 + [2] * 20)
    age = np.array(list(range(1, 21)) * 2, dtype=float)
    lap = np.arange(2, 42, dtype=float)
    time = 91.25 + predict_offsets(params, comp, age, lap)
    assert abs(driver_intercept(params, comp, age, lap, time) - 91.25) < 1e-9

"""Synthetic races with known coefficients, for tests across racemodel, ETL and API."""

import numpy as np

from .fit import LapSet, design

# offset MEDIUM, HARD; deg1 S/M/H; deg2 S/M/H; trend
TRUE_BETA = np.array([0.45, 0.9, 0.08, 0.05, 0.03, 0.002, 0.001, 0.0005, -0.06])


def synthetic_laps(
    n_groups: int = 40, laps: int = 55, sigma: float = 0.3, seed: int = 1, beta=TRUE_BETA
) -> LapSet:
    """Each driver-race: two stints (pit at a random lap), own intercept, Gaussian noise."""
    rng = np.random.default_rng(seed)
    g, comp, age, lap = [], [], [], []
    for grp in range(n_groups):
        pit = int(rng.integers(15, 40))
        c1, c2 = rng.choice(3, size=2, replace=False)
        for lp in range(2, laps + 1):  # lap 1 excluded, as in the real filter
            first = lp <= pit
            g.append(grp)
            comp.append(c1 if first else c2)
            age.append(lp if first else lp - pit)
            lap.append(lp)
    group = np.array(g)
    compound = np.array(comp)
    age_a = np.array(age, dtype=float)
    lap_a = np.array(lap, dtype=float)
    intercepts = rng.normal(90.0, 0.8, n_groups)
    time = intercepts[group] + design(compound, age_a, lap_a) @ beta
    time += rng.normal(0.0, sigma, len(time))
    return LapSet(group=group, compound=compound, age=age_a, lap=lap_a, time=time)

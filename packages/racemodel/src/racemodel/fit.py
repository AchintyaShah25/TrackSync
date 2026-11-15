"""Fit the lap-time model (decision 0020).

Each driver-race gets its own intercept (car + driver pace that day), removed with the
within-group transform. The shared coefficients are compound offsets, quadratic tyre
degradation per compound, and one lap trend (fuel burn + track evolution). A circuit's
coefficients are ridge-shrunk toward the global fit, so sparse circuits borrow strength.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .types import COMPOUND_INDEX, DRY_COMPOUNDS, PaceParams

N_COEF = 9  # offset MEDIUM, HARD; deg1 x3; deg2 x3; trend
GROSS_SLOW = 1.07  # drop laps slower than 107% of the driver-race median
OUTLIER_SIGMAS = 3.0
# Prior strength in pseudo-laps: a circuit with this many clean laps lands halfway
# between its own estimate and the global one.
PRIOR_LAPS = 500.0  # tuned by the backtest (evals/racemodel)


@dataclass
class LapSet:
    """Clean dry laps. Arrays are aligned; `group` identifies a driver-race."""

    group: np.ndarray  # int
    compound: np.ndarray  # int index into DRY_COMPOUNDS
    age: np.ndarray  # tyre age in laps
    lap: np.ndarray  # lap number
    time: np.ndarray  # seconds

    def __len__(self) -> int:
        return len(self.time)

    def take(self, mask: np.ndarray) -> LapSet:
        return LapSet(
            *(a[mask] for a in (self.group, self.compound, self.age, self.lap, self.time))
        )

    @classmethod
    def from_rows(cls, rows: list[tuple[object, str, int, int, float]]) -> LapSet:
        """rows: (group_key, compound, tyre_age, lap, seconds); non-dry compounds dropped."""
        keep = [r for r in rows if r[1] in COMPOUND_INDEX]
        keys: dict[object, int] = {}
        group = np.array([keys.setdefault(r[0], len(keys)) for r in keep], dtype=np.int64)
        return cls(
            group=group,
            compound=np.array([COMPOUND_INDEX[r[1]] for r in keep], dtype=np.int64),
            age=np.array([r[2] for r in keep], dtype=np.float64),
            lap=np.array([r[3] for r in keep], dtype=np.float64),
            time=np.array([r[4] for r in keep], dtype=np.float64),
        )


def design(compound: np.ndarray, age: np.ndarray, lap: np.ndarray) -> np.ndarray:
    """Columns: [is_MEDIUM, is_HARD, age*is_c (x3), age^2*is_c (x3), lap]."""
    n = len(age)
    x = np.zeros((n, N_COEF))
    for c in range(len(DRY_COMPOUNDS)):
        is_c = compound == c
        if c > 0:
            x[:, c - 1] = is_c
        x[:, 2 + c] = age * is_c
        x[:, 5 + c] = age * age * is_c
    x[:, 8] = lap
    return x


def _demean(values: np.ndarray, group: np.ndarray) -> np.ndarray:
    n_groups = int(group.max()) + 1
    # Groups emptied by filtering have count 0; they are never indexed, so avoid 0/0.
    counts = np.maximum(np.bincount(group, minlength=n_groups), 1).astype(np.float64)
    if values.ndim == 1:
        means = np.bincount(group, weights=values, minlength=n_groups) / counts
        return values - means[group]
    out = np.empty_like(values)
    for j in range(values.shape[1]):
        means = np.bincount(group, weights=values[:, j], minlength=n_groups) / counts
        out[:, j] = values[:, j] - means[group]
    return out


def _gross_filter(laps: LapSet) -> LapSet:
    n_groups = int(laps.group.max()) + 1
    med = np.zeros(n_groups)
    for g in np.unique(laps.group):
        med[g] = np.median(laps.time[laps.group == g])
    return laps.take(laps.time <= GROSS_SLOW * med[laps.group])


def _solve(
    laps: LapSet, prior: np.ndarray | None, prior_laps: float
) -> tuple[np.ndarray, np.ndarray]:
    x = _demean(design(laps.compound, laps.age, laps.lap), laps.group)
    y = _demean(laps.time, laps.group)
    xtx = x.T @ x
    xty = x.T @ y
    n = max(len(laps), 1)
    # Penalty per coefficient scaled to its data precision, so PRIOR_LAPS reads as laps.
    scale = np.maximum(np.diag(xtx) / n, 1e-9)
    if prior is None:
        lam = np.diag(scale * 1e-6)
        prior = np.zeros(N_COEF)
    else:
        lam = np.diag(scale * prior_laps)
    beta = np.linalg.solve(xtx + lam, xty + lam @ prior)
    return beta, y - x @ beta


def robust_sigma(r: np.ndarray) -> float:
    if len(r) == 0:
        return 0.0
    return float(1.4826 * np.median(np.abs(r - np.median(r))))


def fit_pace(
    laps: LapSet, prior: np.ndarray | None = None, prior_laps: float = PRIOR_LAPS
) -> tuple[PaceParams, dict]:
    """Fit coefficients; with `prior` (a global coef vector) shrink toward it.

    Returns the params and fit metrics (laps used, residual sigma).
    """
    if len(laps) == 0:
        if prior is None:
            raise ValueError("no laps to fit and no prior")
        params = PaceParams.from_coef_vector(list(prior), sigma=0.8, age_max=[30, 40, 50])
        return params, {"n_laps": 0, "n_groups": 0, "sigma": params.sigma}
    laps = _gross_filter(laps)
    beta, resid = _solve(laps, prior, prior_laps)
    for _ in range(2):  # drop residual outliers, refit
        sigma = robust_sigma(resid)
        keep = np.abs(resid) <= OUTLIER_SIGMAS * max(sigma, 1e-6)
        if keep.all():
            break
        laps = laps.take(keep)
        beta, resid = _solve(laps, prior, prior_laps)
    sigma = robust_sigma(resid)
    age_max = [
        int(laps.age[laps.compound == c].max()) if (laps.compound == c).any() else 30
        for c in range(len(DRY_COMPOUNDS))
    ]
    params = PaceParams.from_coef_vector([float(b) for b in beta], sigma, age_max)
    metrics = {
        "n_laps": len(laps),
        "n_groups": len(np.unique(laps.group)),
        "sigma": round(sigma, 4),
    }
    return params, metrics


def deg_curve(params: PaceParams, compound: int, age: np.ndarray) -> np.ndarray:
    """Seconds lost to tyre age, extrapolated linearly (never improving) past observed ages."""
    a_max = float(max(params.age_max[compound], 1))
    d1, d2 = params.deg1[compound], params.deg2[compound]
    a = np.minimum(age, a_max)
    base = d1 * a + d2 * a * a
    slope = max(d1 + 2 * d2 * a_max, 0.0)
    return base + slope * np.maximum(age - a_max, 0.0)


def predict_offsets(
    params: PaceParams, compound: np.ndarray, age: np.ndarray, lap: np.ndarray
) -> np.ndarray:
    """Model lap time minus the driver-race intercept."""
    out = np.asarray(params.offset)[compound] + params.trend * lap
    for c in range(len(DRY_COMPOUNDS)):
        m = compound == c
        if m.any():
            out[m] += deg_curve(params, c, age[m])
    return out


def driver_intercept(
    params: PaceParams, compound: np.ndarray, age: np.ndarray, lap: np.ndarray, time: np.ndarray
) -> float:
    """A driver's pace in one race: robust mean of (lap time - model offsets)."""
    if len(time) == 0:
        raise ValueError("no clean laps")
    r = time - predict_offsets(params, compound, age, lap)
    med = np.median(r)
    keep = np.abs(r - med) <= OUTLIER_SIGMAS * max(robust_sigma(r), 0.05)
    return float(np.mean(r[keep]))

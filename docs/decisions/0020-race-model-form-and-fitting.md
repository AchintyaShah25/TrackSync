# 0020: Race model form and fitting

- **Status:** Accepted
- **Date:** 2026-11-15
- **Milestone:** 2

## Context
The strategy forecaster needs a lap-time model per circuit that the ETL can fit from our
own data (2023+ OpenF1 laps) and the API can evaluate cheaply. Constraints:
- **Sparse data:** each circuit has at most 4 races in the database.
- **Laps to drop:** lap 1, pit in/out laps, laps under SC, VSC or red flag, inaccurate or
  deleted laps, and wet laps.
- **Light dependencies:** pure Python + NumPy only (architecture rule 2), so no statsmodels
  or scikit-learn.
- **Pace differs by driver and race:** car, driver and conditions all change pace. The
  model has to separate that from tyre effects.

## Options considered
1. **Per-stint linear fits, then averaging:** simple, but stints are short and noisy, and
   a stint's intercept and slope trade off against each other.
2. **One regression per circuit with a fixed effect for each driver-race:** the intercept
   absorbs car, driver and conditions. The shared coefficients (compound offsets,
   degradation, lap trend) are fitted across all drivers. NumPy least squares handles it
   after the within-group transform.
3. **Hierarchical Bayesian model (PyMC):** the best way to share information between
   circuits, but it adds a heavy dependency and is slow to fit in CI.

## Decision
Option 2, with ridge shrinkage toward a global fit to get most of option 3's benefit.

`lap_time = intercept[driver-race] + offset[c] + deg1[c]·age + deg2[c]·age² + trend·lap + noise`

- **Compounds:** SOFT, MEDIUM, HARD. Offsets are relative to SOFT.
- **One combined `trend` term:** fuel burn and track evolution are both linear in the lap
  number, so the data cannot tell them apart.
- **Global fit:** fitted on all dry races first. Each circuit is then fitted with a penalty
  `(β − β_global)ᵀ Λ (β − β_global)`. Λ is scaled so its strength reads as pseudo-laps
  (`PRIOR_LAPS`, starting at 500 and tuned by the backtest). A circuit with 500 clean laps
  ends up halfway between its own fit and the global one.
- **Outliers:** laps slower than 107% of the driver-race median are dropped, then two
  passes drop residuals beyond 3 robust σ.
- **Extrapolation:** past the oldest tyre age seen at a circuit, degradation continues as
  a straight line and never improves. Without that, a fitted quadratic can bend downward
  and make very long stints look fast.

## Consequences
- The fit takes seconds, so the ETL refits every circuit on each run.
- **First real fit (local data, 69k clean laps):**
  - Lap trend is −0.05 s/lap, which matches the known fuel effect.
  - Degradation is 0.8–2.0 s after 20 laps, with Bahrain the highest.
  - Residual σ is 0.33–0.46 s; Monaco is 1.16 s because of traffic.
- **Known weakness:** the SOFT-to-HARD pace gap comes out small (about 0.03 s globally).
  Teams choose compounds for a reason (softs run early, in traffic and under tyre
  management), so race data understates the raw pace gap. The backtest measures whether
  this hurts lap-time prediction. If the forecasts look wrong for soft-heavy strategies,
  revisit with a compound-offset prior taken from qualifying data.
- **Same-name compounds differ by circuit:** "SOFT" means a different Pirelli compound
  (C3, C4 or C5) at different circuits. Fitting each circuit separately absorbs that; the
  global prior only pulls toward an average.

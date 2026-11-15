# 0021: Monte Carlo race simulator design

- **Status:** Accepted
- **Date:** 2026-11-15
- **Milestone:** 2

## Context
`POST /strategy/simulate` compares up to 3 pit strategies for one driver in a past dry
race, using the circuit model from decision 0020. It runs on Render's free instance
(small CPU, under 1.5 s per response, SPEC M2). The result has to show uncertainty,
meaning the spread of outcomes (the fan chart), not just one number.

## Options considered
1. **Deterministic sum of lap times:** instant, but shows no risk at all, and safety cars
   are the main reason strategies win or lose.
2. **Simulating the full field (all 20 cars, overtakes, traffic):** realistic, but it
   needs an overtaking model we can't validate with our data, and it is slow.
3. **Simulating only the driver, with a randomized race and the rest of the field fixed:**
   fast, with an uncertainty we can explain. Its limits are listed below.

## Decision
Option 3, vectorized in NumPy as `(runs × laps)` arrays, 500 runs by default.

- **Random race:**
  - SC and VSC deployments are Poisson with per-circuit rates, shrunk toward the pooled
    history (`PRIOR_RACES = 4`).
  - Start laps are drawn from the pooled distribution of start points (as a fraction of
    race distance), and durations from the pooled distribution of durations.
  - A red flag (track status 5) counts as an SC.
  - A lap is neutralized only if most drivers' laps carry the status.
- **Pace noise:** independent per lap, from N(0, σ_circuit).
- **Pit stops:**
  - Loss is per-circuit, measured as in-lap + out-lap − 2 × the driver's clean median, on
    green dry stops only. It is shrunk toward the global median (`PRIOR_STOPS = 20`).
  - Each stop is drawn from N(loss, pooled robust sd), floored at 70% of the loss.
  - A stop under SC costs 0.5 × the loss and under VSC 0.65 × (fixed priors). The measured
    loss under neutralization mixes the slower reference laps with the stop itself, so
    the ratio could not be fitted cleanly.
- **Common random numbers:** all strategies in one call share the same random race: SCs,
  lap noise and a per-run tyre-wear multiplier. Pit-crew draws are independent per
  strategy, because stop luck is real variance between plans. Two copies of the same
  strategy are identical until the first stop and then differ only by pit luck.
- **Tyre-wear uncertainty:** each run scales degradation by a mean-1 lognormal factor.
  Its log-sd (`deg_cv`) is the robust spread of per-race wear against the circuit fit:
  0.31 on 2023–2026 data. Without it, a replay with no safety cars showed strategy gaps
  with zero spread, which is false certainty.
- **Neutralized laps add the same time to every car.** There is no field compression. A
  car that is 10 s behind at an SC does not close up.
- **Finishing position:**
  - The driver's actual strategy is always simulated as a hidden reference.
  - For each run, `simulated finish = actual finish time + (strategy − actual strategy)`.
    The position comes from ranking that time against the other drivers' actual race times.
  - This cancels shared biases, such as standing-start time and absolute SC lap time.
  - `p_gain` = P(position < actual position). It is only available when the driver
    finished on the lead lap.
- **Determinism:** a `seed` makes every call reproducible, for static pages and tests.
- **SC source:** past races can also use the race's real neutralizations
  (`fixed_periods`), so you can ask "with what actually happened, would X have won?".

## Consequences
- 500 runs × 4 strategies × 70 laps simulates in milliseconds, so the 1.5 s budget is
  spent on the database and the network, not on simulating.
- **No field compression or traffic**, so the model understates how much an SC helps a
  car that is behind. The forecast page says so in an "about this model" note.
- **The rest of the field is fixed**, so "would X have won?" assumes rivals keep their
  real race times. That's acceptable for a what-if tool, but it is not a full race
  simulation.
- **Revisit when** a validated overtaking model or a field simulation fits the free CPU
  budget, or when pit-under-SC data can be separated cleanly enough to fit the SC/VSC
  factors.

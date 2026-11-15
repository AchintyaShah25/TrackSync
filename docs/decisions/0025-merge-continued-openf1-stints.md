# 0025: Merge OpenF1 stints that continue the same tyre set

- **Status:** Accepted
- **Date:** 2026-11-16
- **Milestone:** 2 (fixes Milestone 1 data)

## Context
While choosing the forecast showcase, the simulator claimed a one-stop would have made
Verstappen about 45 s faster at Canada 2025. The race ended behind the safety car, and
OpenF1's `stints` feed opened one-lap stints 4, 5 and 6 for every car on laps 67–70 without
a tyre change (`tyre_age_at_start` 30, 31, 32 on the same hard set). Stored as-is, these
caused three problems:
- the Milestone 1 strategy chart showed three phantom stops;
- the forecaster charged pit loss for each one in the "real" reference strategy;
- 426 of 5,917 stored stints (7%) were such continuations.

## Options considered
1. **Fix in the API and web, at read time:** every reader would need the same rule, and
   the strategy chart would still be wrong.
2. **Merge in the ETL at the raw OpenF1 level, before building laps and stints:** one rule,
   one place, and the laps' `stint` numbers stay consistent with the stints table.
3. **Use the `pit` feed to decide which stints are real:** the pit feed has the same
   phantom entries under the safety car (laps 67–69 are marked pit-in), so it doesn't help.

## Decision
Option 2. `merge_continued_stints()` (`services/etl/tracksync_etl/transform/laps.py`)
merges a stint into the previous one when:
- the compound matches, and
- its starting tyre age equals the previous stint's starting age plus the laps run on it
  (within one lap).

It then renumbers each car's stints 1..n. Both `build_laps` and `build_stints` use the
cleaned list. A genuine same-compound stop puts on a set with a different age, so it is
still counted.

## Consequences
- Production needs a reload of all seasons (from the ETL cache, about 2 minutes) for the
  cleaned stints to replace the phantom ones; `etl.yml` does it on a manual dispatch per
  season.
- Laps keep their `pit_in` flags from the pit feed. They only exclude laps from fitting,
  which is harmless for laps already under the SC.
- The regression test is the Canada 2025 case (test_laps_transform).

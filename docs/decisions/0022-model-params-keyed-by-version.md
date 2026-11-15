# 0022: Store fitted model params per circuit, keyed by model version

- **Status:** Accepted
- **Date:** 2026-11-16
- **Milestone:** 2

## Context
The ETL fits the race model (decision 0020) and the API reads it to simulate (decision
0021). SPEC §3 sketched `circuit_model_params(circuit_id, season_window, params jsonb,
fitted_at, metrics jsonb)`. Two things about how this is used shape the key:
- The weekly ETL refits after every load.
- A change to how the model is fitted (new coefficients, different filters) has to ship
  without breaking an API that is still running the old code.

## Options considered
1. **Key by `(circuit_id, season_window)` as sketched:** keeps history by time window,
   but nothing reads old windows. A logic change would also overwrite rows the deployed
   API still expects in the old format.
2. **Key by `(circuit_id, model_version)`:** `racemodel.MODEL_VERSION` is bumped
   whenever the meaning of the params changes. The new ETL writes new rows, the old API
   keeps reading its own version, and the new API reads the new rows after deploy.
3. **One row per circuit, no version:** simplest, but a deploy-order race: whichever of
   ETL or API ships first would break the other.

## Decision
Option 2. Primary key `(circuit_id, model_version)`:
- `params` holds `CircuitParams.to_dict()`.
- `metrics` holds the fit diagnostics (laps used, residual σ, races, prior strength).
- `n_races` and `n_laps` are columns so they're easy to query.

Every ETL run that loads laps refits all circuits, an idempotent upsert that takes about
1 s for 100k laps. `tracksync-etl --fit-models` refits without ingesting anything. A
failed fit marks the run `failed` (red CI job) but keeps the loaded data.

Reads are public through RLS like the other F1 tables. Only the ETL writes.

## Consequences
- **Small:** 26 rows, about 88 kB per version. Old versions can be deleted by hand once
  no deployed API reads them.
- **Deploy order:** a version bump means running `--fit-models` on production before (or
  with) the API deploy that reads the new version.
- **Season windows:** the fit uses every race from 2023 on. If old seasons start to hurt
  accuracy (rule changes), add a window *inside* the fit and bump the version. The key
  doesn't need to change.

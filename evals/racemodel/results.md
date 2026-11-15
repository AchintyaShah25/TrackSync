# Race model backtest

Generated 2026-11-15T12:23:05+00:00 by `make eval` ([backtest.py](backtest.py)).

Leave-one-race-out. Each driver's pace comes from their first 5 clean laps; every later clean lap is predicted from compound, tyre age and lap.
Prior strength tuned on 22 dry 2025 races (chosen: 1000 pseudo-laps); reported on 16 dry 2026 races (13,867 laps, 778 stints). 8 wet races excluded.

| Predictor | Lap MAE (s) | Lap median AE (s) | Stint mean-pace MAE (s) |
|---|---|---|---|
| Flat (driver's early median) | 1.219 | 1.042 | 1.033 |
| Fuel/track trend only | 0.984 | 0.765 | 0.822 |
| **Full model** | **0.817** | **0.578** | **0.633** |

Lap MAE by compound (full model): HARD 0.796 s, MEDIUM 0.795 s, SOFT 0.883 s

Validation lap MAE by prior strength (pseudo-laps): 100: 0.869, 250: 0.848, 500: 0.829, 1000: 0.808, 2000: 0.812

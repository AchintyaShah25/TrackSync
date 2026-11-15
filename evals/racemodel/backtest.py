"""Leave-one-race-out backtest of the lap-time model (SPEC M2, decision 0020).

For every held-out dry race: fit all circuits on every *other* race, estimate each
driver's pace from their first CALIB clean laps of that race, then predict each later
clean lap from its compound, tyre age and lap number. Compare with two baselines:

- flat:  the driver's median of the first CALIB laps (no tyres, no fuel)
- trend: flat + the fitted lap trend (fuel/track only, no tyre model)

The prior strength is tuned on 2025 races (validation) and the final numbers are reported
on 2026 races (test), so tuning never sees the test races.

Run: make eval   (reads DATABASE_URL, default local Supabase)
"""

from __future__ import annotations

import json
import os
import statistics
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from racemodel.dataset import RaceLap, fit_circuits, racing_laps, wet_events
from racemodel.fit import driver_intercept, predict_offsets
from racemodel.types import COMPOUND_INDEX
from tracksync_etl.fit_models import load_race_laps
from tracksync_etl.load.db import make_engine

CALIB = 5
MIN_EVAL = 5  # a driver needs this many clean laps after calibration to be scored
PRIOR_GRID = [100.0, 250.0, 500.0, 1000.0, 2000.0]
OUT = Path(__file__).parent


def _arrays(laps: list[RaceLap]):
    comp = np.array([COMPOUND_INDEX[r.compound] for r in laps])  # type: ignore[index]
    age = np.array([r.tyre_life for r in laps], dtype=float)
    lap = np.array([r.lap for r in laps], dtype=float)
    t = np.array([r.time for r in laps], dtype=float)
    return comp, age, lap, t


def score_race(rows: list[RaceLap], event_id: int, prior_laps: float) -> dict | None:
    race = [r for r in rows if r.event_id == event_id]
    fits = fit_circuits(rows, exclude_events=frozenset({event_id}), prior_laps=prior_laps)
    cid = race[0].circuit_id
    if cid not in fits:
        return None  # new circuit: nothing to learn from
    pace = fits[cid].params.pace
    by_driver: dict[str, list[RaceLap]] = defaultdict(list)
    for r in race:
        by_driver[r.driver_id].append(r)
    by_driver = {d: racing_laps(laps) for d, laps in by_driver.items()}
    err = {"model": [], "flat": [], "trend": []}
    per_compound: dict[str, list[float]] = defaultdict(list)
    stint_err = {"model": [], "flat": [], "trend": []}
    for laps in by_driver.values():
        laps.sort(key=lambda r: r.lap)
        if len(laps) < CALIB + MIN_EVAL:
            continue
        cal, test = laps[:CALIB], laps[CALIB:]
        cc, ca, cl, ct = _arrays(cal)
        tc, ta, tl, tt = _arrays(test)
        icpt = driver_intercept(pace, cc, ca, cl, ct)
        flat0 = float(np.median(ct))
        preds = {
            "model": icpt + predict_offsets(pace, tc, ta, tl),
            "flat": np.full(len(tt), flat0),
            "trend": flat0 + pace.trend * (tl - float(np.median(cl))),
        }
        for k, p in preds.items():
            err[k] += list(np.abs(p - tt))
        for r, e in zip(test, np.abs(preds["model"] - tt), strict=True):
            per_compound[r.compound].append(float(e))  # type: ignore[index]
        # Stint-level: error of the mean lap time over each (compound, stint) block.
        stints: dict[tuple, list[int]] = defaultdict(list)
        for i, r in enumerate(test):
            stints[(r.compound, r.lap - r.tyre_life)].append(i)  # type: ignore[operator]
        for idx in stints.values():
            if len(idx) >= 3:
                for k, p in preds.items():
                    stint_err[k].append(abs(float(np.mean(p[idx]) - np.mean(tt[idx]))))
    if not err["model"]:
        return None
    return {"err": err, "per_compound": per_compound, "stint_err": stint_err}


def evaluate(rows: list[RaceLap], events: list[int], prior_laps: float) -> dict:
    err = {"model": [], "flat": [], "trend": []}
    stint_err = {"model": [], "flat": [], "trend": []}
    per_compound: dict[str, list[float]] = defaultdict(list)
    scored = 0
    for e in events:
        res = score_race(rows, e, prior_laps)
        if res is None:
            continue
        scored += 1
        for k in err:
            err[k] += res["err"][k]
            stint_err[k] += res["stint_err"][k]
        for c, v in res["per_compound"].items():
            per_compound[c] += v
    mae = {k: round(statistics.fmean(v), 4) for k, v in err.items()}
    medae = {k: round(statistics.median(v), 4) for k, v in err.items()}
    smae = {k: round(statistics.fmean(v), 4) for k, v in stint_err.items() if v}
    return {
        "races": scored,
        "laps": len(err["model"]),
        "stints": len(stint_err["model"]),
        "lap_mae_s": mae,
        "lap_median_ae_s": medae,
        "stint_mean_mae_s": smae,
        "lap_mae_by_compound_s": {
            c: round(statistics.fmean(v), 4) for c, v in sorted(per_compound.items())
        },
    }


def main() -> int:
    url = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:54322/postgres")
    with make_engine(url).connect() as conn:
        rows = load_race_laps(conn)
    if not rows:
        print("no race laps in the database; load data first (make etl)")
        return 1
    wet = wet_events(rows)
    dry_events = sorted({r.event_id for r in rows} - wet)
    val = [e for e in dry_events if e // 100 == 2025]
    test = [e for e in dry_events if e // 100 == 2026]
    t0 = time.monotonic()

    tuning = {}
    for prior in PRIOR_GRID:
        res = evaluate(rows, val, prior)
        tuning[str(int(prior))] = res["lap_mae_s"]["model"]
        print(f"validation 2025, prior_laps={prior:>6}: lap MAE {res['lap_mae_s']}", flush=True)
    best = float(min(tuning, key=lambda k: tuning[k]))
    final = evaluate(rows, test, best)
    print(f"test 2026, prior_laps={best}: {final}", flush=True)

    report = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "calibration_laps": CALIB,
        "validation": {"season": 2025, "races": len(val), "lap_mae_by_prior": tuning},
        "chosen_prior_laps": best,
        "test": {"season": 2026, **final},
        "wet_races_excluded": len(wet),
        "seconds": round(time.monotonic() - t0),
    }
    (OUT / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    m = final["lap_mae_s"]
    md = final["lap_median_ae_s"]
    s = final["stint_mean_mae_s"]
    lines = [
        "# Race model backtest",
        "",
        f"Generated {report['generated_at']} by `make eval` ([backtest.py](backtest.py)).",
        "",
        "Leave-one-race-out. Each driver's pace comes from their first "
        f"{CALIB} clean laps; every later clean lap is predicted from compound, tyre age and lap.",
        f"Prior strength tuned on {len(val)} dry 2025 races (chosen: {int(best)} pseudo-laps); "
        f"reported on {final['races']} dry 2026 races ({final['laps']:,} laps, "
        f"{final['stints']} stints). {len(wet)} wet races excluded.",
        "",
        "| Predictor | Lap MAE (s) | Lap median AE (s) | Stint mean-pace MAE (s) |",
        "|---|---|---|---|",
        f"| Flat (driver's early median) | {m['flat']:.3f} | {md['flat']:.3f} "
        f"| {s.get('flat', float('nan')):.3f} |",
        f"| Fuel/track trend only | {m['trend']:.3f} | {md['trend']:.3f} "
        f"| {s.get('trend', float('nan')):.3f} |",
        f"| **Full model** | **{m['model']:.3f}** | **{md['model']:.3f}** "
        f"| **{s.get('model', float('nan')):.3f}** |",
        "",
        "Lap MAE by compound (full model): "
        + ", ".join(f"{c} {v:.3f} s" for c, v in final["lap_mae_by_compound_s"].items()),
        "",
        "Validation lap MAE by prior strength (pseudo-laps): "
        + ", ".join(f"{k}: {v:.3f}" for k, v in tuning.items()),
        "",
    ]
    (OUT / "results.md").write_text("\n".join(lines))
    print(f"wrote {OUT / 'results.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

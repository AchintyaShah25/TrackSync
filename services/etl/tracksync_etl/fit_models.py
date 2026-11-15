"""Refit the race model for every circuit and store it (SPEC M2, decisions 0020-0022).

Reads all race laps (about 100k rows, a few MB), fits with racemodel, and upserts one
row per circuit for the current MODEL_VERSION. Idempotent: a re-run updates the same rows.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from racemodel import MODEL_VERSION
from racemodel.dataset import RaceLap, fit_circuits
from sqlalchemy import Connection, text

from .load.db import Store

log = logging.getLogger(__name__)

RACE_LAPS_SQL = text(
    """
    select l.event_id, e.circuit_id, l.driver_id, l.lap, l.lap_time_ms, l.compound,
           l.tyre_life, l.pit_in, l.pit_out, l.track_status, l.is_accurate, l.deleted
    from public.laps l
    join public.events e on e.id = l.event_id
    where l.session = 'R'
    order by l.event_id, l.driver_id, l.lap
    """
)


def load_race_laps(conn: Connection) -> list[RaceLap]:
    return [
        RaceLap(
            event_id=r.event_id,
            circuit_id=r.circuit_id,
            driver_id=r.driver_id,
            lap=r.lap,
            time=r.lap_time_ms / 1000.0 if r.lap_time_ms is not None else None,
            compound=r.compound,
            tyre_life=r.tyre_life,
            pit_in=r.pit_in,
            pit_out=r.pit_out,
            status=r.track_status,
            is_accurate=r.is_accurate,
            deleted=r.deleted,
        )
        for r in conn.execute(RACE_LAPS_SQL)
    ]


def refit_all(store: Store) -> int:
    """Fit and upsert params for every circuit with race laps. Returns rows written."""
    with store.engine.connect() as conn:
        laps = load_race_laps(conn)
    if not laps:
        log.info("model fit: no race laps yet")
        return 0
    fits = fit_circuits(laps)
    for f in fits.values():  # Postgres jsonb rejects NaN/Infinity: fail loudly here
        json.dumps([f.params.to_dict(), f.metrics], allow_nan=False)
    now = datetime.now(UTC)
    rows = [
        {
            "circuit_id": cid,
            "model_version": MODEL_VERSION,
            "params": f.params.to_dict(),
            "metrics": f.metrics,
            "n_races": f.n_races,
            "n_laps": f.n_laps,
            "fitted_at": now,
        }
        for cid, f in fits.items()
    ]
    with store.engine.begin() as conn:
        store.upsert(conn, "circuit_model_params", rows)
    log.info("model fit: %d circuits from %d race laps (v%d)", len(rows), len(laps), MODEL_VERSION)
    return len(rows)

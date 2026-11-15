"""Idempotent writes to Postgres with SQLAlchemy Core + psycopg 3.

- Reference tables (seasons, circuits, events, drivers, teams, driver_teams, standings)
  are upserted on their primary key.
- Event-scoped tables (results, laps, stints, fastest_lap_traces) are replaced per
  (event_id, session) inside one transaction: delete, then insert. A re-run therefore
  leaves identical row counts and never leaves stale rows behind.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Connection, Engine, MetaData, Table, create_engine, delete, func, select
from sqlalchemy.dialects.postgresql import insert

TABLES = [
    "seasons",
    "circuits",
    "events",
    "drivers",
    "teams",
    "driver_teams",
    "results",
    "laps",
    "stints",
    "fastest_lap_traces",
    "standings",
    "etl_runs",
    "circuit_model_params",
]
EVENT_SCOPED = ["results", "laps", "stints", "fastest_lap_traces"]
_BATCH = 2000


def make_engine(database_url: str) -> Engine:
    url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return create_engine(url, pool_pre_ping=True)


class Store:
    def __init__(self, engine: Engine):
        self.engine = engine
        md = MetaData()
        md.reflect(engine, only=TABLES, schema="public")
        self.t: dict[str, Table] = {name: md.tables[f"public.{name}"] for name in TABLES}

    # ---------------------------------------------------------------- primitives

    def upsert(
        self,
        conn: Connection,
        table: str,
        rows: Sequence[dict[str, Any]],
        *,
        update: Iterable[str] | None = None,
    ) -> int:
        """Insert rows; on primary-key conflict update `update` columns (default: all non-PK)."""
        if not rows:
            return 0
        t = self.t[table]
        pk = [c.name for c in t.primary_key.columns]
        cols = list(update) if update is not None else [c for c in rows[0] if c not in pk]
        for i in range(0, len(rows), _BATCH):
            stmt = insert(t).values(list(rows[i : i + _BATCH]))
            if cols:
                set_ = {c: stmt.excluded[c] for c in cols}
                if "updated_at" in t.c:
                    set_["updated_at"] = func.now()
                stmt = stmt.on_conflict_do_update(index_elements=pk, set_=set_)
            else:
                stmt = stmt.on_conflict_do_nothing(index_elements=pk)
            conn.execute(stmt)
        return len(rows)

    def replace_session(
        self, conn: Connection, table: str, event_id: int, session: str, rows: list[dict]
    ) -> int:
        t = self.t[table]
        conn.execute(delete(t).where(t.c.event_id == event_id, t.c.session == session))
        for i in range(0, len(rows), _BATCH):
            conn.execute(insert(t).values(rows[i : i + _BATCH]))
        return len(rows)

    # ---------------------------------------------------------------- queries

    def count(self, conn: Connection, table: str, event_id: int | None = None) -> int:
        t = self.t[table]
        q = select(func.count()).select_from(t)
        if event_id is not None:
            q = q.where(t.c.event_id == event_id)
        return conn.execute(q).scalar_one()

    def has_session_data(self, conn: Connection, event_id: int) -> bool:
        """An event counts as ingested once it has race results and race laps."""
        r, la = self.t["results"], self.t["laps"]
        has_results = conn.execute(
            select(func.count()).where(r.c.event_id == event_id, r.c.session == "R")
        ).scalar_one()
        has_laps = conn.execute(
            select(func.count()).where(la.c.event_id == event_id, la.c.session == "R")
        ).scalar_one()
        return bool(has_results and has_laps)

    def circuit_has_outline(self, conn: Connection, circuit_id: str) -> bool:
        c = self.t["circuits"]
        return (
            conn.execute(select(c.c.outline).where(c.c.id == circuit_id)).scalar_one_or_none()
            is not None
        )

    # ---------------------------------------------------------------- run log

    def start_run(self, args: dict[str, Any]) -> int:
        with self.engine.begin() as conn:
            t = self.t["etl_runs"]
            return conn.execute(
                insert(t).values(args=json.loads(json.dumps(args, default=str))).returning(t.c.id)
            ).scalar_one()

    def finish_run(
        self, run_id: int, status: str, row_counts: dict[str, Any], error: str | None = None
    ) -> None:
        with self.engine.begin() as conn:
            t = self.t["etl_runs"]
            conn.execute(
                t.update()
                .where(t.c.id == run_id)
                .values(
                    finished_at=datetime.now(UTC),
                    status=status,
                    row_counts=row_counts,
                    error=error,
                )
            )

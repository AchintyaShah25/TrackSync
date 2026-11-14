"""Schedule → circuits and events rows (Jolpica schedule DataFrame)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pandas as pd

from .common import clean, event_id, slugify, to_int

# Jolpica schedule columns → our session codes, in weekend order.
SESSION_COLUMNS = [
    ("FP1", "Practice 1", "fp1"),
    ("FP2", "Practice 2", "fp2"),
    ("FP3", "Practice 3", "fp3"),
    ("SQ", "Sprint Qualifying", "sprintQualifying"),
    ("S", "Sprint", "sprint"),
    ("Q", "Qualifying", "qualifying"),
    ("R", "Race", "race"),
]


def _session_start(row: pd.Series, prefix: str) -> datetime | None:
    date = clean(row.get(f"{prefix}Date"))
    if date is None:
        return None
    ts = pd.Timestamp(date)
    time_val = clean(row.get(f"{prefix}Time"))
    if time_val is not None:
        if isinstance(time_val, pd.Timedelta):
            ts = ts.normalize() + time_val
        else:
            ts = pd.Timestamp(f"{ts.date()} {str(time_val).rstrip('Z')}")
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts.tz_convert("UTC").to_pydatetime()


def circuit_row(row: pd.Series) -> dict[str, Any]:
    return {
        "id": row["circuitId"],
        "name": row["circuitName"],
        "locality": clean(row.get("locality")),
        "country": clean(row.get("country")),
    }


def event_rows(season: int, schedule: pd.DataFrame) -> tuple[list[dict], list[dict]]:
    """Return (circuits, events) rows for a season's schedule. Circuits are deduplicated."""
    circuits: dict[str, dict] = {}
    events: list[dict] = []
    for _, row in schedule.iterrows():
        rnd = to_int(row["round"])
        circuits[row["circuitId"]] = circuit_row(row)
        sessions = []
        for code, name, prefix in SESSION_COLUMNS:
            start = _session_start(row, prefix)
            if start is not None:
                sessions.append({"code": code, "name": name, "start_utc": start.isoformat()})
        race_start = _session_start(row, "race")
        is_sprint = any(s["code"] == "S" for s in sessions)
        events.append(
            {
                "id": event_id(season, rnd),
                "season": season,
                "round": rnd,
                "circuit_id": row["circuitId"],
                "name": row["raceName"],
                "slug": slugify(row["raceName"]),
                "format": "sprint" if is_sprint else "conventional",
                "race_start_utc": race_start,
                "sessions": sessions,
            }
        )
    return list(circuits.values()), events


def is_completed(event: dict, now: datetime | None = None, margin_hours: float = 4) -> bool:
    """True once the race should have finished (start + margin) relative to `now`."""
    now = now or datetime.now(UTC)
    start = event["race_start_utc"]
    return start is not None and (now - start).total_seconds() > margin_hours * 3600

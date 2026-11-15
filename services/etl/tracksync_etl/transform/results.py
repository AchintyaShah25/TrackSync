"""Jolpica result frames → drivers, teams, driver_teams and results rows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from .common import clean, timedelta_ms, to_int


@dataclass
class ResultBundle:
    drivers: dict[str, dict] = field(default_factory=dict)
    teams: dict[str, dict] = field(default_factory=dict)
    driver_teams: set[tuple[str, int, str]] = field(default_factory=set)
    results: list[dict] = field(default_factory=list)
    # driver number (as raced in this event) → Jolpica driverId, used to map OpenF1 rows
    number_to_driver: dict[int, str] = field(default_factory=dict)

    def driver_team_rows(self) -> list[dict]:
        return [
            {"driver_id": d, "season": s, "team_id": t} for d, s, t in sorted(self.driver_teams)
        ]


def _register(bundle: ResultBundle, row: pd.Series, season: int) -> tuple[str, str]:
    driver_id = row["driverId"]
    team_id = row["constructorId"]
    bundle.drivers[driver_id] = {
        "id": driver_id,
        "code": clean(row.get("driverCode")) or driver_id[:3].upper(),
        "full_name": f"{row['givenName']} {row['familyName']}",
        "number": to_int(row.get("driverNumber")),
    }
    bundle.teams.setdefault(
        team_id,
        {"id": team_id, "season": season, "name": row["constructorName"], "color_hex": None},
    )
    bundle.driver_teams.add((driver_id, season, team_id))
    raced_number = to_int(row.get("number"))
    if raced_number is not None:
        bundle.number_to_driver[raced_number] = driver_id
    return driver_id, team_id


def add_race_like(
    bundle: ResultBundle, event_id: int, season: int, session: str, df: pd.DataFrame
) -> None:
    """Race or sprint results. time_ms is the total race time (null if lapped/DNF)."""
    for _, row in df.iterrows():
        driver_id, team_id = _register(bundle, row, season)
        bundle.results.append(
            {
                "event_id": event_id,
                "session": session,
                "driver_id": driver_id,
                "team_id": team_id,
                "position": _classified_position(row),
                "grid": to_int(row.get("grid")),
                "points": float(clean(row.get("points")) or 0),
                "status": clean(row.get("status")),
                # Lapped cars' total time covers fewer laps; the UI uses laps for them.
                "time_ms": to_int(row.get("totalRaceTimeMillis")),
                "laps": to_int(row.get("laps")),
            }
        )


def _classified_position(row: pd.Series) -> int | None:
    # positionText is 'R', 'D', 'W', ... when not classified.
    text = str(clean(row.get("positionText")) or "")
    return to_int(row.get("position")) if text.isdigit() or not text else None


def add_qualifying(bundle: ResultBundle, event_id: int, season: int, df: pd.DataFrame) -> None:
    """Qualifying results. time_ms is the driver's best time across Q1-Q3."""
    for _, row in df.iterrows():
        driver_id, team_id = _register(bundle, row, season)
        times = [timedelta_ms(row.get(q)) for q in ("Q1", "Q2", "Q3")]
        best = min((t for t in times if t), default=None)
        bundle.results.append(
            {
                "event_id": event_id,
                "session": "Q",
                "driver_id": driver_id,
                "team_id": team_id,
                "position": to_int(row.get("position")),
                "grid": None,
                "points": 0.0,
                "status": None,
                "time_ms": best,
                "laps": None,
            }
        )


def apply_team_colors(bundle: ResultBundle, openf1_drivers: list[dict[str, Any]]) -> None:
    """Fill teams.color_hex from OpenF1's team_colour, mapped through driver numbers."""
    team_of = {d: t for d, _, t in bundle.driver_teams}
    for d in openf1_drivers:
        colour = d.get("team_colour")
        driver_id = bundle.number_to_driver.get(d.get("driver_number"))
        if not colour or driver_id is None or driver_id not in team_of:
            continue
        team = bundle.teams[team_of[driver_id]]
        if team["color_hex"] is None:
            team["color_hex"] = "#" + colour.strip("#").upper()

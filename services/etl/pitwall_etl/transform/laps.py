"""OpenF1 laps, stints, pit, position and race_control → laps and stints rows.

OpenF1 has no per-lap track status, in-lap flag, position or accuracy flag, so they are
derived here (docs/decisions/0004). Track status codes follow FastF1's convention so
Milestone 2's fitting can filter on them: 1 green, 4 safety car, 5 red flag,
6 virtual safety car, 7 VSC ending. Sector yellows (2) are not tracked.
"""

from __future__ import annotations

import logging
from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

Row = dict[str, Any]
log = logging.getLogger(__name__)

# Laps are at least this long; used to close an SC window one lap after "IN THIS LAP".
_SC_IN_LAP_TAIL = timedelta(seconds=150)
_VSC_ENDING_TAIL = timedelta(seconds=15)


def parse_ts(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


@dataclass(frozen=True)
class StatusWindow:
    code: str
    start: datetime
    end: datetime

    def overlaps(self, start: datetime, end: datetime) -> bool:
        return self.start < end and start < self.end


def status_windows(race_control: list[Row], session_end: datetime) -> list[StatusWindow]:
    """Build SC / VSC / red-flag time windows from race control messages."""
    msgs = sorted((m for m in race_control if m.get("date")), key=lambda m: m["date"])
    windows: list[StatusWindow] = []
    sc_start = vsc_start = red_start = None
    for m in msgs:
        t = parse_ts(m["date"])
        text = (m.get("message") or "").upper()
        flag = (m.get("flag") or "").upper()
        category = m.get("category")
        if category == "SafetyCar" and red_start:
            # A red-flagged race often resumes behind the safety car with no track-wide
            # GREEN flag (e.g. Brazil 2024), so any SC/VSC message ends the red period.
            windows.append(StatusWindow("5", red_start, t))
            red_start = None
        if category == "SafetyCar":
            if "VIRTUAL SAFETY CAR DEPLOYED" in text:
                vsc_start = t
            elif "VIRTUAL SAFETY CAR ENDING" in text and vsc_start:
                windows.append(StatusWindow("6", vsc_start, t))
                windows.append(StatusWindow("7", t, t + _VSC_ENDING_TAIL))
                vsc_start = None
            elif "SAFETY CAR DEPLOYED" in text:
                sc_start = sc_start or t
            elif "SAFETY CAR IN THIS LAP" in text and sc_start:
                windows.append(StatusWindow("4", sc_start, t + _SC_IN_LAP_TAIL))
                sc_start = None
        elif category == "Flag" and m.get("scope") == "Track":
            if flag == "RED":
                red_start = red_start or t
                if sc_start:  # a red flag ends the SC period that preceded it
                    windows.append(StatusWindow("4", sc_start, t))
                    sc_start = None
            elif flag in ("GREEN", "CHEQUERED") and red_start:
                windows.append(StatusWindow("5", red_start, t))
                red_start = None
    for code, start in (("4", sc_start), ("6", vsc_start), ("5", red_start)):
        if start:
            windows.append(StatusWindow(code, start, session_end))
    return windows


def lap_status(windows: list[StatusWindow], start: datetime, end: datetime) -> str:
    codes = sorted({w.code for w in windows if w.overlaps(start, end)})
    return "".join(codes) if codes else "1"


def _position_lookup(positions: list[Row]) -> dict[int, tuple[list[datetime], list[int]]]:
    by_driver: dict[int, list[tuple[datetime, int]]] = {}
    for p in positions:
        if p.get("date") and p.get("position") is not None:
            by_driver.setdefault(p["driver_number"], []).append(
                (parse_ts(p["date"]), p["position"])
            )
    out = {}
    for num, items in by_driver.items():
        items.sort()
        out[num] = ([t for t, _ in items], [pos for _, pos in items])
    return out


def _position_at(lookup, number: int, t: datetime) -> int | None:
    if number not in lookup:
        return None
    times, values = lookup[number]
    i = bisect_right(times, t) - 1
    return values[i] if i >= 0 else None


def build_laps(
    *,
    event_id: int,
    session: str,
    laps: list[Row],
    stints: list[Row],
    pits: list[Row],
    positions: list[Row],
    race_control: list[Row],
    session_end: datetime,
    number_to_driver: dict[int, str],
) -> list[Row]:
    """One row per (driver, lap). Drivers OpenF1 knows but Jolpica does not are skipped."""
    windows = status_windows(race_control, session_end)
    pos_lookup = _position_lookup(positions)
    pit_laps = {(p["driver_number"], p["lap_number"]) for p in pits if p.get("lap_number")}
    stint_of: dict[int, list[Row]] = {}
    for s in stints:
        stint_of.setdefault(s["driver_number"], []).append(s)

    # Lap end = next lap's start for the same driver, else start + duration.
    starts: dict[tuple[int, int], datetime] = {}
    for lap in laps:
        if lap.get("date_start"):
            starts[(lap["driver_number"], lap["lap_number"])] = parse_ts(lap["date_start"])

    rows: list[Row] = []
    for lap in sorted(laps, key=lambda r: (r["driver_number"], r["lap_number"])):
        number, n = lap["driver_number"], lap["lap_number"]
        driver_id = number_to_driver.get(number)
        if driver_id is None or n is None:
            continue
        duration = lap.get("lap_duration")
        start = starts.get((number, n))
        end = starts.get((number, n + 1))
        if end is None and start is not None and duration:
            end = start + timedelta(seconds=duration)

        stint = _stint_for(stint_of.get(number, []), n)
        tyre_life = None
        if stint is not None and stint.get("tyre_age_at_start") is not None:
            tyre_life = stint["tyre_age_at_start"] + (n - stint["lap_start"]) + 1

        pit_in = (number, n) in pit_laps
        pit_out = bool(lap.get("is_pit_out_lap"))
        status = lap_status(windows, start, end) if start and end else None
        rows.append(
            {
                "event_id": event_id,
                "session": session,
                "driver_id": driver_id,
                "lap": n,
                "lap_time_ms": round(duration * 1000) if duration else None,
                "compound": stint.get("compound") if stint else None,
                "tyre_life": tyre_life,
                "stint": stint.get("stint_number") if stint else None,
                "position": _position_at(pos_lookup, number, end) if end else None,
                "pit_in": pit_in,
                "pit_out": pit_out,
                "track_status": status,
                "is_accurate": bool(duration) and n > 1 and not pit_in and not pit_out,
                "deleted": False,
            }
        )
    return rows


def _stint_for(stints: list[Row], lap: int) -> Row | None:
    for s in stints:
        start, end = s.get("lap_start"), s.get("lap_end")
        if start is not None and end is not None and start <= lap <= end:
            return s
    return None


def build_stints(
    *, event_id: int, session: str, stints: list[Row], number_to_driver: dict[int, str]
) -> list[Row]:
    rows = []
    for s in stints:
        driver_id = number_to_driver.get(s["driver_number"])
        if driver_id is None or s.get("lap_start") is None or s.get("lap_end") is None:
            continue
        if s["lap_end"] < s["lap_start"]:
            # OpenF1 reports e.g. laps 1-0 for cars that retired before completing a lap
            # (Australia 2023); such a stint has no laps to draw.
            log.warning("dropping stint with invalid laps %s", s)
            continue
        rows.append(
            {
                "event_id": event_id,
                "session": session,
                "driver_id": driver_id,
                "stint": s["stint_number"],
                "compound": (s.get("compound") or None),
                "start_lap": s["lap_start"],
                "end_lap": s["lap_end"],
            }
        )
    # OpenF1 occasionally repeats a stint number; keep the last occurrence.
    dedup = {(r["driver_id"], r["stint"]): r for r in rows}
    return list(dedup.values())

"""Orchestrates one season or event: fetch (sources) → transform (pure) → load (db)."""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from statistics import median
from typing import Any

from sqlalchemy import select

from .load.db import Store
from .sources import circuit_info as circuit_source
from .sources import jolpica
from .sources.openf1 import OpenF1Client
from .transform import geometry, laps, reference, results
from .transform.common import to_int

log = logging.getLogger(__name__)

# Our session code → OpenF1 session_name(s).
OPENF1_NAMES = {
    "R": ("Race",),
    "S": ("Sprint",),
    "Q": ("Qualifying",),
}
LAP_SESSIONS = ("R", "S")
TRACE_SESSIONS = ("Q", "R")
# OpenF1 data for a session can still be filling in for a while; don't cache it before then.
CACHE_AFTER = timedelta(days=3)


def _fmt(ts: datetime) -> str:
    """OpenF1 date filter value: naive UTC ISO without '+00:00' ('+' breaks query strings)."""
    return ts.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]


@dataclass
class EventReport:
    event_id: int
    counts: Counter = field(default_factory=Counter)
    skipped: list[str] = field(default_factory=list)


class Pipeline:
    def __init__(
        self,
        store: Store | None,
        openf1: OpenF1Client,
        *,
        now: datetime | None = None,
        refresh_circuits: bool = False,
        jolpica_source=jolpica,
        circuit_info_source=circuit_source,
    ):
        self.store = store  # None = dry run
        self.openf1 = openf1
        self.now = now or datetime.now(UTC)
        self.refresh_circuits = refresh_circuits
        self.jolpica = jolpica_source
        self.circuit_info = circuit_info_source
        self._openf1_sessions: dict[int, list[dict]] = {}

    # ---------------------------------------------------------------- schedule

    def ingest_schedule(self, season: int) -> list[dict]:
        circuits, events = reference.event_rows(season, self.jolpica.schedule(season))
        if self.store:
            with self.store.engine.begin() as conn:
                self.store.upsert(conn, "seasons", [{"year": season}])
                self.store.upsert(
                    conn, "circuits", circuits, update=["name", "locality", "country"]
                )
                self.store.upsert(conn, "events", events)
        log.info("season %d: %d events in schedule", season, len(events))
        return events

    def ingest_standings(self, season: int) -> int:
        rows = []
        for kind, (df, after) in (
            ("driver", self.jolpica.driver_standings(season)),
            ("constructor", self.jolpica.constructor_standings(season)),
        ):
            id_col = "driverId" if kind == "driver" else "constructorId"
            for _, r in df.iterrows():
                rows.append(
                    {
                        "season": season,
                        "kind": kind,
                        "entity_id": r[id_col],
                        "position": to_int(r.get("position")),
                        "points": float(r.get("points") or 0),
                        "wins": to_int(r.get("wins")) or 0,
                        "after_round": after or 0,
                    }
                )
        if self.store and rows:
            with self.store.engine.begin() as conn:
                t = self.store.t["standings"]
                # A snapshot replaces the previous one (drivers can drop out of a season).
                conn.execute(t.delete().where(t.c.season == season))
                self.store.upsert(conn, "standings", rows)
        return len(rows)

    # ---------------------------------------------------------------- OpenF1 lookup

    def _sessions_for(self, season: int) -> list[dict]:
        if season not in self._openf1_sessions:
            self._openf1_sessions[season] = self.openf1.get(
                "sessions", year=season, cache=season < self.now.year
            )
        return self._openf1_sessions[season]

    def openf1_sessions(self, event: dict) -> dict[str, dict]:
        """Our session code → OpenF1 session, matched through the race date."""
        sessions = self._sessions_for(event["season"])
        race_day = event["race_start_utc"].date()
        meeting = next(
            (
                s["meeting_key"]
                for s in sessions
                if s.get("session_name") == "Race"
                and datetime.fromisoformat(s["date_start"]).date() == race_day
            ),
            None,
        )
        if meeting is None:
            return {}
        out = {}
        for s in sessions:
            if s["meeting_key"] != meeting:
                continue
            for code, names in OPENF1_NAMES.items():
                if s.get("session_name") in names:
                    out[code] = s
        return out

    def _get(self, endpoint: str, session: dict, **params: Any) -> list[dict]:
        ended = datetime.fromisoformat(session["date_end"])
        return self.openf1.get(
            endpoint,
            session_key=session["session_key"],
            cache=self.now - ended > CACHE_AFTER,
            **params,
        )

    # ---------------------------------------------------------------- one event

    def ingest_event(self, event: dict) -> EventReport:
        season, rnd, eid = event["season"], event["round"], event["id"]
        report = EventReport(eid)
        log.info("event %d (%s)", eid, event["name"])

        bundle = results.ResultBundle()
        results.add_race_like(bundle, eid, season, "R", self.jolpica.race_results(season, rnd))
        if event["format"] == "sprint":
            results.add_race_like(
                bundle, eid, season, "S", self.jolpica.sprint_results(season, rnd)
            )
        results.add_qualifying(bundle, eid, season, self.jolpica.qualifying_results(season, rnd))
        if not bundle.results:
            report.skipped.append("no Jolpica results yet")
            return report

        of1 = self.openf1_sessions(event)
        if not of1:
            report.skipped.append("no OpenF1 meeting found")

        session_laps: dict[str, list[dict]] = {}
        lap_rows: dict[str, list[dict]] = {}
        stint_rows: dict[str, list[dict]] = {}
        for code in LAP_SESSIONS:
            s = of1.get(code)
            if s is None:
                continue
            if code == "R":
                results.apply_team_colors(bundle, self._get("drivers", s))
            raw_laps = self._get("laps", s)
            session_laps[code] = raw_laps
            raw_stints = self._get("stints", s)
            lap_rows[code] = laps.build_laps(
                event_id=eid,
                session=code,
                laps=raw_laps,
                stints=raw_stints,
                pits=self._get("pit", s),
                positions=self._get("position", s),
                race_control=self._get("race_control", s),
                session_end=datetime.fromisoformat(s["date_end"]),
                number_to_driver=bundle.number_to_driver,
            )
            stint_rows[code] = laps.build_stints(
                event_id=eid,
                session=code,
                stints=raw_stints,
                number_to_driver=bundle.number_to_driver,
            )
            if not raw_laps:
                report.skipped.append(f"{code}: OpenF1 laps not available yet")

        traces, circuit_update = self._traces_and_outline(event, of1, session_laps, bundle, report)

        if self.store is None:
            report.counts.update(
                results=len(bundle.results),
                laps=sum(map(len, lap_rows.values())),
                stints=sum(map(len, stint_rows.values())),
                fastest_lap_traces=sum(map(len, traces.values())),
            )
            return report

        st = self.store
        with st.engine.begin() as conn:
            st.upsert(conn, "drivers", list(bundle.drivers.values()))
            colored = [t for t in bundle.teams.values() if t["color_hex"]]
            plain = [t for t in bundle.teams.values() if not t["color_hex"]]
            st.upsert(conn, "teams", colored, update=["name", "color_hex"])
            st.upsert(conn, "teams", plain, update=["name"])
            st.upsert(conn, "driver_teams", bundle.driver_team_rows())
            for code in ("R", "S", "Q"):
                rows = [r for r in bundle.results if r["session"] == code]
                if rows:
                    report.counts["results"] += st.replace_session(conn, "results", eid, code, rows)
            for code, rows in lap_rows.items():
                if rows:
                    report.counts["laps"] += st.replace_session(conn, "laps", eid, code, rows)
            for code, rows in stint_rows.items():
                if rows:
                    report.counts["stints"] += st.replace_session(conn, "stints", eid, code, rows)
            for code, rows in traces.items():
                if rows:
                    report.counts["fastest_lap_traces"] += st.replace_session(
                        conn, "fastest_lap_traces", eid, code, rows
                    )
            if circuit_update:
                c = st.t["circuits"]
                current = conn.execute(
                    select(c.c.outline_event_id).where(c.c.id == event["circuit_id"])
                ).scalar_one_or_none()
                if self.refresh_circuits or current is None or eid >= current:
                    conn.execute(
                        c.update().where(c.c.id == event["circuit_id"]).values(**circuit_update)
                    )
                    report.counts["circuit_outline"] = 1
        return report

    # ---------------------------------------------------------------- traces

    def _fastest_laps(self, raw_laps: list[dict], bundle: results.ResultBundle) -> list[dict]:
        best: dict[int, dict] = {}
        for lap in raw_laps:
            if (
                not lap.get("lap_duration")
                or not lap.get("date_start")
                or lap.get("is_pit_out_lap")
            ):
                continue
            if lap["driver_number"] not in bundle.number_to_driver:
                continue
            cur = best.get(lap["driver_number"])
            if cur is None or lap["lap_duration"] < cur["lap_duration"]:
                best[lap["driver_number"]] = lap
        return sorted(best.values(), key=lambda r: r["lap_duration"])

    def _lap_samples(self, session: dict, lap: dict) -> geometry.LapSamples | None:
        start = datetime.fromisoformat(lap["date_start"])
        window = {
            "driver_number": lap["driver_number"],
            "date>": _fmt(start - timedelta(seconds=1)),
            "date<": _fmt(start + timedelta(seconds=lap["lap_duration"] + 1)),
        }
        car = self._get("car_data", session, **window)
        loc = self._get("location", session, **window)
        return geometry.lap_samples(car, loc, lap["date_start"], lap["lap_duration"])

    def _traces_and_outline(self, event, of1, session_laps, bundle, report):
        traces: dict[str, list[dict]] = {}
        circuit_update: dict[str, Any] | None = None
        frame: geometry.Frame | None = None
        ref_length: float | None = None

        for code in ("Q", "R"):  # Q first: its pole lap defines the frame and the outline
            s = of1.get(code)
            if s is None:
                continue
            raw = session_laps.get(code) or self._get("laps", s)
            fastest = self._fastest_laps(raw, bundle)
            samples = [(lap, self._lap_samples(s, lap)) for lap in fastest]
            samples = [(lap, smp) for lap, smp in samples if smp is not None]
            if not samples:
                report.skipped.append(f"{code}: no telemetry")
                continue
            if frame is None:
                info = self.circuit_info.fetch(event["season"], s["circuit_key"])
                rotation = info.rotation_deg if info else 0.0
                outline, frame = geometry.build_outline(samples[0][1], rotation)
                ref_length = median(geometry.lap_length(smp) for _, smp in samples)
                corners = (
                    geometry.build_corners(info.corners.to_dict("records"), frame) if info else []
                )
                circuit_update = {
                    "outline": outline,
                    "corners": corners,
                    "rotation_deg": rotation,
                    "length_m": round(ref_length),
                    "outline_event_id": event["id"],
                }
            traces[code] = [
                {
                    "event_id": event["id"],
                    "session": code,
                    "driver_id": bundle.number_to_driver[lap["driver_number"]],
                    "lap": lap["lap_number"],
                    "lap_time_ms": round(lap["lap_duration"] * 1000),
                    "points": geometry.build_trace(smp, ref_length, frame),
                }
                for lap, smp in samples
            ]
        return traces, circuit_update

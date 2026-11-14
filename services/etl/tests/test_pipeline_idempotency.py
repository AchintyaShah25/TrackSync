"""End-to-end ETL load against a real Postgres, using fixtures and fake sources."""

from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import pytest
from pitwall_etl.load.db import Store, make_engine
from pitwall_etl.pipeline import Pipeline
from pitwall_etl.sources.circuit_info import CircuitInfo
from sqlalchemy import text

pytestmark = pytest.mark.db

QUALI_START = datetime(2024, 8, 31, 14, 0, tzinfo=UTC)
RACE_START = datetime(2024, 9, 1, 13, 0, tzinfo=UTC)
NUMBERS = [16, 81, 4, 55]


class FakeJolpica:
    def __init__(self, load):
        self.load = load

    def schedule(self, season):
        return self.load("jolpica_schedule_2024_r15-17.json")

    def race_results(self, season, rnd):
        return self.load("jolpica_race_2024_16_top4.json") if rnd == 16 else pd.DataFrame()

    def sprint_results(self, season, rnd):
        return pd.DataFrame()

    def qualifying_results(self, season, rnd):
        return self.load("jolpica_quali_2024_16_top4.json") if rnd == 16 else pd.DataFrame()

    def driver_standings(self, season):
        df = pd.DataFrame([{"driverId": "leclerc", "position": 1, "points": 25.0, "wins": 1}])
        return df, 16

    def constructor_standings(self, season):
        return pd.DataFrame(
            [{"constructorId": "ferrari", "position": 1, "points": 25.0, "wins": 1}]
        ), 16


class FakeCircuitInfo:
    @staticmethod
    def fetch(year, circuit_key):
        corners = pd.DataFrame([{"X": 1000.0, "Y": 0.0, "Number": 1, "Letter": "", "Angle": 0.0}])
        return CircuitInfo(rotation_deg=95.0, corners=corners)


def _laps(start: datetime, n_laps: int, lap_s: float) -> list[dict]:
    rows = []
    for i, num in enumerate(NUMBERS):
        for lap in range(1, n_laps + 1):
            rows.append(
                {
                    "driver_number": num,
                    "lap_number": lap,
                    "date_start": (start + timedelta(seconds=(lap - 1) * lap_s + i)).isoformat(),
                    "lap_duration": lap_s + i * 0.1 + (0.5 if lap == 1 else 0),
                    "is_pit_out_lap": lap == 3,
                }
            )
    return rows


def _samples(params, lap_s=80.0, hz=3.7):
    """Synthetic circular lap for whatever window the pipeline asks for."""
    t0 = datetime.fromisoformat(params["date>"]).replace(tzinfo=UTC)
    t1 = datetime.fromisoformat(params["date<"]).replace(tzinfo=UTC)
    ts = np.arange(0, (t1 - t0).total_seconds(), 1 / hz)
    car, loc = [], []
    for s in ts:
        date = (t0 + timedelta(seconds=float(s))).isoformat()
        a = 2 * np.pi * s / lap_s
        car.append({"date": date, "speed": 250, "throttle": 90, "brake": 0, "n_gear": 7})
        loc.append({"date": date, "x": 1000 * np.cos(a), "y": 1000 * np.sin(a)})
    return car, loc


class FakeOpenF1:
    requests_made = 0

    def get(self, endpoint, *, cache=True, **params):
        sk = params.get("session_key")
        if endpoint == "sessions":
            base = {"meeting_key": 1244, "circuit_key": 39}
            return [
                {
                    **base,
                    "session_key": 9586,
                    "session_name": "Qualifying",
                    "date_start": QUALI_START.isoformat(),
                    "date_end": (QUALI_START + timedelta(hours=1)).isoformat(),
                },
                {
                    **base,
                    "session_key": 9590,
                    "session_name": "Race",
                    "date_start": RACE_START.isoformat(),
                    "date_end": (RACE_START + timedelta(hours=2)).isoformat(),
                },
            ]
        if endpoint == "drivers":
            return [{"driver_number": n, "team_colour": "E8002D"} for n in NUMBERS]
        if endpoint == "laps":
            return _laps(QUALI_START if sk == 9586 else RACE_START, 3 if sk == 9586 else 6, 80.0)
        if endpoint == "stints":
            return [
                {
                    "driver_number": n,
                    "stint_number": 1,
                    "lap_start": 1,
                    "lap_end": 2,
                    "compound": "MEDIUM",
                    "tyre_age_at_start": 0,
                }
                for n in NUMBERS
            ] + [
                {
                    "driver_number": n,
                    "stint_number": 2,
                    "lap_start": 3,
                    "lap_end": 6,
                    "compound": "HARD",
                    "tyre_age_at_start": 0,
                }
                for n in NUMBERS
            ]
        if endpoint == "pit":
            return [{"driver_number": n, "lap_number": 2} for n in NUMBERS]
        if endpoint == "position":
            return [
                {"driver_number": n, "date": RACE_START.isoformat(), "position": i + 1}
                for i, n in enumerate(NUMBERS)
            ]
        if endpoint == "race_control":
            return []
        if endpoint in ("car_data", "location"):
            car, loc = _samples(params)
            return car if endpoint == "car_data" else loc
        raise AssertionError(endpoint)


COUNT_SQL = """
select (select count(*) from results), (select count(*) from laps), (select count(*) from stints),
       (select count(*) from fastest_lap_traces), (select count(*) from drivers),
       (select count(*) from teams), (select count(*) from events), (select count(*) from standings)
"""


@pytest.fixture
def store(test_db_url):
    st = Store(make_engine(test_db_url))
    yield st
    st.engine.dispose()


def run_once(store, fixture_frame):
    pipe = Pipeline(
        store,
        FakeOpenF1(),
        now=datetime(2024, 9, 10, tzinfo=UTC),
        jolpica_source=FakeJolpica(fixture_frame),
        circuit_info_source=FakeCircuitInfo,
    )
    events = pipe.ingest_schedule(2024)
    monza = next(e for e in events if e["round"] == 16)
    report = pipe.ingest_event(monza)
    pipe.ingest_standings(2024)
    return report


def test_rerunning_an_event_changes_no_row_counts(store, fixture_frame):
    """Ingesting the same event twice leaves every table's row count unchanged.

    Why: this is a Milestone 1 acceptance criterion; the weekly cron and manual re-runs
    must never duplicate data (docs/decisions/0005).
    """
    first = run_once(store, fixture_frame)
    with store.engine.connect() as conn:
        before = conn.execute(text(COUNT_SQL)).one()
    second = run_once(store, fixture_frame)
    with store.engine.connect() as conn:
        after = conn.execute(text(COUNT_SQL)).one()
    assert before == after
    assert first.counts == second.counts
    results, laps, stints, traces, *_ = after
    assert results == 8  # 4 race + 4 quali
    assert laps == 24 and stints == 8
    assert traces == 8  # Q + R fastest laps for 4 drivers


def test_loaded_rows_have_derived_fields_and_circuit_outline(store, fixture_frame):
    """The load writes team colors, derived lap flags, columnar traces and an outline.

    Why: these are the fields the API and charts read; a silent null here would only
    surface as a blank chart.
    """
    run_once(store, fixture_frame)
    with store.engine.connect() as conn:
        color = conn.execute(text("select color_hex from teams where id='ferrari'")).scalar()
        pit_in = conn.execute(
            text("select count(*) from laps where event_id=202416 and pit_in")
        ).scalar()
        trace = conn.execute(
            text("select points from fastest_lap_traces where session='Q' limit 1")
        ).scalar()
        outline, corners, rotation = conn.execute(
            text("select outline, corners, rotation_deg from circuits where id='monza'")
        ).one()
    assert color == "#E8002D"
    assert pit_in == 4
    assert len(trace["speed"]) == 300
    assert len(outline["x"]) == 400 and corners[0]["number"] == 1 and rotation == 95.0

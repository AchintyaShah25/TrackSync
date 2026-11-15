"""Race-model fitting against a real Postgres seeded with synthetic laps."""

import numpy as np
import psycopg
import pytest
from racemodel import MODEL_VERSION, CircuitParams
from racemodel.synthetic import TRUE_BETA, synthetic_laps
from racemodel.types import DRY_COMPOUNDS
from sqlalchemy import text
from tracksync_etl.fit_models import refit_all
from tracksync_etl.load.db import Store, make_engine

pytestmark = pytest.mark.db

DRIVERS = ["leclerc", "norris", "piastri", "sainz"]


def _seed(url: str) -> None:
    laps = synthetic_laps(n_groups=8, laps=40, seed=11)
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("insert into seasons (year) values (2023), (2024)")
        conn.execute("insert into circuits (id, name) values ('monza', 'Monza')")
        for season in (2023, 2024):
            conn.execute(
                "insert into events (id, season, round, circuit_id, name, slug, format) "
                "values (%s, %s, 16, 'monza', 'Italian GP', 'italian-grand-prix', 'conventional')",
                (season * 100 + 16, season),
            )
        for d in DRIVERS:
            conn.execute(
                "insert into drivers (id, code, full_name) values (%s, %s, %s)",
                (d, d[:3].upper(), d.title()),
            )
        rows = []
        for i in range(len(laps)):
            g = int(laps.group[i])
            event = 202316 if g < 4 else 202416
            rows.append(
                (
                    event, DRIVERS[g % 4], int(laps.lap[i]), round(laps.time[i] * 1000),
                    DRY_COMPOUNDS[laps.compound[i]], int(laps.age[i]),
                    "4" if 20 <= laps.lap[i] <= 22 else "1",  # one SC period per race
                )
            )  # fmt: skip
        with conn.cursor() as cur:
            cur.executemany(
                "insert into laps (event_id, session, driver_id, lap, lap_time_ms, compound, "
                "tyre_life, track_status, is_accurate) values (%s,'R',%s,%s,%s,%s,%s,%s,true)",
                rows,
            )


@pytest.fixture(scope="module")
def store(fresh_database):
    url = fresh_database("tracksync_test_fit")
    _seed(url)
    st = Store(make_engine(url))
    yield st
    st.engine.dispose()


def test_refit_writes_one_row_per_circuit_and_is_idempotent(store):
    """Refitting twice leaves one params row per circuit for the current model version.

    Why: the weekly ETL refits after every load; re-runs must update, never duplicate
    (decision 0005), and the API reads exactly one row per circuit and version.
    """
    assert refit_all(store) == 1
    assert refit_all(store) == 1
    with store.engine.connect() as conn:
        rows = conn.execute(
            text("select circuit_id, model_version, n_races, n_laps from circuit_model_params")
        ).all()
    assert rows == [("monza", MODEL_VERSION, 2, rows[0].n_laps)]
    assert rows[0].n_laps > 200


def test_stored_params_round_trip_and_are_sensible(store):
    """Stored JSON loads back into CircuitParams with the synthetic truth recovered.

    Why: the API deserializes this row for every simulation; a schema drift between
    racemodel and the stored JSON would only show up as a 500 in production.
    """
    refit_all(store)
    with store.engine.connect() as conn:
        raw = conn.execute(text("select params from circuit_model_params")).scalar_one()
    params = CircuitParams.from_dict(raw)
    assert params.circuit_id == "monza"
    assert abs(params.pace.trend - TRUE_BETA[8]) < 0.03
    assert np.isfinite(params.pace.coef_vector()).all()
    # Both races had one SC period (laps 20-22), so the rate is near one per race.
    assert 0.5 < params.events.sc_rate <= 1.0

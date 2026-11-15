"""POST /strategy/simulate and GET /strategy/params against a dedicated seeded database."""

import gzip
import json
import time

import httpx
import psycopg
import pytest
from app.config import Settings
from app.main import create_app
from app.ratelimit import TokenBucket, client_key
from racemodel import MODEL_VERSION
from racemodel.dataset import RaceLap, fit_circuits
from racemodel.synthetic import synthetic_laps
from racemodel.types import DRY_COMPOUNDS
from starlette.requests import Request

from .conftest import SEED

pytestmark = pytest.mark.db

LAPS = 30
DRY = 202417  # Monza, fitted
UNFITTED = 202418  # Las Vegas, dry, no params row
WET = 202419  # Las Vegas, wet
DRIVERS = ["leclerc", "norris", "piastri", "sainz"]
TEAM = {"leclerc": "ferrari", "norris": "mclaren", "piastri": "mclaren", "sainz": "ferrari"}


def _race_laps(event_id: int, circuit: str, seed: int, wet: bool = False) -> list[RaceLap]:
    syn = synthetic_laps(n_groups=4, laps=LAPS, seed=seed)
    out = []
    for i in range(len(syn)):
        g = int(syn.group[i])
        compound = "INTERMEDIATE" if wet else DRY_COMPOUNDS[syn.compound[i]]
        out.append(
            RaceLap(
                event_id, circuit, DRIVERS[g], int(syn.lap[i]), float(syn.time[i]), compound,
                int(syn.age[i]), False, False, "4" if 12 <= syn.lap[i] <= 13 else "1",
            )
        )  # fmt: skip
    return out


def _stints(laps: list[RaceLap], driver: str) -> list[tuple[str, int, int]]:
    """(compound, start, end) blocks from a driver's laps; lap 1 joins the first stint."""
    mine = sorted((r for r in laps if r.driver_id == driver), key=lambda r: r.lap)
    blocks: list[list] = []
    for r in mine:
        if blocks and blocks[-1][0] == r.compound and r.tyre_life != 1:
            blocks[-1][2] = r.lap
        else:
            blocks.append([r.compound, r.lap, r.lap])
    blocks[0][1] = 1
    return [tuple(b) for b in blocks]


def _seed(url: str) -> None:
    dry = _race_laps(DRY, "monza", 21) + _race_laps(202316, "monza", 22)
    unfitted = _race_laps(UNFITTED, "las_vegas", 23)
    wet = _race_laps(WET, "las_vegas", 24, wet=True)
    fit = fit_circuits([r for r in dry if r.event_id == DRY] + _race_laps(202316, "monza", 22))
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(SEED.read_text())
        conn.execute(
            "insert into drivers (id, code, full_name) values "
            "('piastri', 'PIA', 'Oscar Piastri'), ('sainz', 'SAI', 'Carlos Sainz')"
        )
        for eid, circuit in ((DRY, "monza"), (UNFITTED, "las_vegas"), (WET, "las_vegas")):
            conn.execute(
                "insert into events (id, season, round, circuit_id, name, slug, format) "
                "values (%s, 2024, %s, %s, 'Test GP', 'test-gp', 'conventional')",
                (eid, eid % 100, circuit),
            )
        with conn.cursor() as cur:
            for laps in (dry, unfitted, wet):
                event_laps = [r for r in laps if r.event_id != 202316]
                cur.executemany(
                    "insert into laps (event_id, session, driver_id, lap, lap_time_ms, compound,"
                    " tyre_life, track_status, is_accurate) values (%s,'R',%s,%s,%s,%s,%s,%s,true)",
                    [
                        (r.event_id, r.driver_id, r.lap, round(r.time * 1000), r.compound,
                         r.tyre_life, r.status)
                        for r in event_laps
                    ],
                )  # fmt: skip
                eid = event_laps[0].event_id
                for d_i, d in enumerate(DRIVERS):
                    finished = not (eid == DRY and d == "sainz")
                    cur.execute(
                        "insert into results (event_id, session, driver_id, team_id, position,"
                        " points, status, time_ms, laps) values (%s,'R',%s,%s,%s,0,%s,%s,%s)",
                        (eid, d, TEAM[d], d_i + 1 if finished else None,
                         "Finished" if finished else "Retired",
                         2_700_000 + d_i * 3000 if finished else None,
                         LAPS if finished else 10),
                    )  # fmt: skip
                    for n, (comp, start, end) in enumerate(_stints(event_laps, d), start=1):
                        cur.execute(
                            "insert into stints (event_id, session, driver_id, stint, compound,"
                            " start_lap, end_lap) values (%s,'R',%s,%s,%s,%s,%s)",
                            (eid, d, n, comp, start, end),
                        )
        conn.execute(
            "insert into circuit_model_params (circuit_id, model_version, params, metrics,"
            " n_races, n_laps) values ('monza', %s, %s, %s, %s, %s)",
            (MODEL_VERSION, json.dumps(fit["monza"].params.to_dict()),
             json.dumps(fit["monza"].metrics), fit["monza"].n_races, fit["monza"].n_laps),
        )  # fmt: skip


@pytest.fixture(scope="module")
def strategy_db(fresh_database) -> str:
    url = fresh_database("tracksync_test_strategy")
    _seed(url)
    return url


async def _client(url: str, **settings):
    app = create_app(Settings(database_url=url, web_origin="http://localhost:3000", **settings))
    return app


@pytest.fixture(scope="module")
async def sclient(strategy_db):
    app = await _client(strategy_db, simulate_per_minute=1000, simulate_global_per_minute=1000)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


def body(**kw) -> dict:
    base = {
        "event_id": DRY,
        "driver_id": "leclerc",
        "seed": 3,
        "runs": 300,
        "strategies": [
            {"label": "One-stop", "stints": [{"compound": "MEDIUM", "laps": 14},
                                             {"compound": "HARD", "laps": 16}]},
            {"label": "Two-stop", "stints": [{"compound": "SOFT", "laps": 9},
                                             {"compound": "MEDIUM", "laps": 11},
                                             {"compound": "SOFT", "laps": 10}]},
        ],
    }  # fmt: skip
    return {**base, **kw}


async def test_simulate_returns_bands_positions_and_actual(sclient):
    """A valid request returns per-lap gap bands, finish deltas and position odds.

    Why: this is the contract the fan chart and summary cards are built on (SPEC M2).
    """
    t0 = time.perf_counter()
    r = await sclient.post("/strategy/simulate", json=body())
    elapsed = time.perf_counter() - t0
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total_laps"] == LAPS and data["driver"]["id"] == "leclerc"
    assert data["actual"]["position"] == 1 and data["actual"]["model_position"] == 1
    assert len(data["strategies"]) == 2
    for s in data["strategies"]:
        assert all(len(s["gap"][k]) == LAPS for k in ("p10", "p25", "p50", "p75", "p90"))
        lo, mid, hi = s["gap"]["p10"][-1], s["gap"]["p50"][-1], s["gap"]["p90"][-1]
        assert lo <= mid <= hi
        assert abs(sum(p["p"] for p in s["positions"]) - 1.0) < 1e-6
        assert 0.0 <= s["p_lose"] <= 1.0 and s["p_gain"] == 0.0  # P1 cannot gain
    assert data["strategies"][1]["stop_laps"] == [9, 20]
    assert len(data["sc_share"]) == LAPS
    assert elapsed < 1.5  # SPEC M2 acceptance
    assert len(gzip.compress(r.content)) < 20_000  # small responses for Render bandwidth


async def test_simulate_is_deterministic_for_a_seed(sclient):
    """The same request and seed give identical results; another seed differs.

    Why: static example pages and shared links must reproduce the same forecast.
    """
    a = (await sclient.post("/strategy/simulate", json=body())).json()
    b = (await sclient.post("/strategy/simulate", json=body())).json()
    c = (await sclient.post("/strategy/simulate", json=body(seed=4))).json()
    assert a == b
    assert a["strategies"][0]["gap"] != c["strategies"][0]["gap"]


async def test_actual_safety_cars_replays_the_race(sclient):
    """safety_cars=actual uses the race's own SC laps for every run.

    Why: "with what actually happened, would X have won?" needs the real neutralizations.
    """
    data = (await sclient.post("/strategy/simulate", json=body(safety_cars="actual"))).json()
    assert data["sc_share"][11] == 1.0 and data["sc_share"][12] == 1.0  # laps 12-13
    assert data["sc_share"][0] == 0.0


@pytest.mark.parametrize(
    ("overrides", "status", "fragment"),
    [
        ({"strategies": [{"label": "H only", "stints": [{"compound": "HARD", "laps": 30}]}]},
         422, "two different compounds"),
        ({"strategies": [{"label": "Short", "stints": [{"compound": "HARD", "laps": 10},
                                                       {"compound": "SOFT", "laps": 10}]}]},
         422, "race is 30 laps"),
        ({"event_id": WET}, 422, "dry races only"),
        ({"event_id": UNFITTED}, 422, "not fitted"),
        ({"driver_id": "sainz"}, 422, "finished this race"),
        ({"driver_id": "hamilton"}, 422, "did not take part"),
        ({"event_id": 209901}, 404, "not found"),
        ({"runs": 5000}, 422, ""),
        ({"strategies": [body()["strategies"][0]] * 4}, 422, ""),
        ({"strategies": [{"label": "Wet", "stints": [{"compound": "WET", "laps": 30}]}]}, 422, ""),
    ],
)  # fmt: skip
async def test_simulate_rejects_invalid_requests(sclient, overrides, status, fragment):
    """Illegal strategies, wet/unfitted races, non-finishers and bad bodies are rejected.

    Why: the user chose to block illegal strategies; every rejection must explain itself.
    """
    r = await sclient.post("/strategy/simulate", json=body(**overrides))
    assert r.status_code == status, r.text
    assert fragment in json.dumps(r.json()["detail"])


async def test_simulate_is_rate_limited_with_retry_after(strategy_db):
    """The third call in a minute from one client gets 429 with Retry-After.

    Why: SPEC section 7 requires simulate rate limits to protect the free CPU.
    """
    app = await _client(strategy_db, simulate_per_minute=2, simulate_global_per_minute=100)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            codes = [
                (await c.post("/strategy/simulate", json=body())).status_code for _ in range(3)
            ]
            limited = await c.post("/strategy/simulate", json=body())
            other = await c.post(
                "/strategy/simulate", json=body(), headers={"X-Forwarded-For": "203.0.113.9"}
            )
    assert codes == [200, 200, 429]
    assert int(limited.headers["retry-after"]) >= 1
    assert other.status_code == 200  # a different client has its own bucket


async def test_params_summary_and_cache_header(sclient):
    """GET /strategy/params/{circuit} returns degradation curves and is publicly cacheable.

    Why: the forecast page's "about this model" panel reads it on every visit.
    """
    r = await sclient.get("/strategy/params/monza")
    assert r.status_code == 200
    data = r.json()
    assert [c["compound"] for c in data["curves"]] == ["SOFT", "MEDIUM", "HARD"]
    assert all(len(c["age"]) == len(c["seconds"]) for c in data["curves"])
    assert "max-age" in r.headers["cache-control"]
    assert (await sclient.get("/strategy/params/las_vegas")).status_code == 404


def test_token_bucket_refills_over_time():
    """A bucket allows `burst` calls, then refills at per_minute/60 tokens per second.

    Why: the limiter is hand-written (no dependency); its arithmetic needs a direct check.
    """
    b = TokenBucket(per_minute=60, burst=2)
    assert b.take("a", now=0.0) == 0 and b.take("a", now=0.0) == 0
    assert b.take("a", now=0.0) == pytest.approx(1.0)
    assert b.take("a", now=1.0) == 0


def test_client_key_uses_first_forwarded_hop():
    """The client key is the first X-Forwarded-For entry, else the socket address.

    Why: on Render every request arrives from the proxy; without this all users would
    share one bucket.
    """
    scope = {
        "type": "http", "headers": [(b"x-forwarded-for", b"198.51.100.7, 10.0.0.1")],
        "client": ("10.0.0.1", 1234),
    }  # fmt: skip
    assert client_key(Request(scope)) == "198.51.100.7"
    assert (
        client_key(Request({"type": "http", "headers": [], "client": ("10.0.0.2", 1)}))
        == "10.0.0.2"
    )

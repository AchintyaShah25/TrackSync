import pytest

pytestmark = pytest.mark.db


async def test_get_event_lists_drivers_in_finishing_order_with_team_colors(client):
    """GET /events/{id} returns the event, its drivers (race order) and available sessions.

    Why: chart selectors are built from this list, colored by team.
    """
    r = await client.get("/events/202416")
    assert r.status_code == 200
    e = r.json()
    assert e["name"] == "Italian Grand Prix"
    assert [d["code"] for d in e["drivers"]] == ["LEC", "NOR"]
    assert e["drivers"][0]["color_hex"] == "#E80020"
    assert e["data_sessions"] == ["Q", "R"] and e["trace_sessions"] == ["Q"]
    assert e["total_laps"] == 5


async def test_get_event_not_found(client):
    """Unknown event ids are 404 on every event route.

    Why: shareable URLs can point at events that do not exist.
    """
    for path in ("", "/results", "/laps", "/stints", "/traces?drivers=VER"):
        assert (await client.get(f"/events/999901{path}")).status_code == 404, path


async def test_results_by_session(client):
    """GET /events/{id}/results returns classified order for the chosen session.

    Why: the race page shows race and qualifying results.
    """
    race = (await client.get("/events/202416/results")).json()
    assert [(r["position"], r["driver"]["id"]) for r in race] == [(1, "leclerc"), (3, "norris")]
    assert race[0]["time_ms"] == 4480727
    quali = (await client.get("/events/202416/results?session=Q")).json()
    assert quali[0]["driver"]["code"] == "NOR"
    assert (await client.get("/events/202416/results?session=S")).json() == []
    assert (await client.get("/events/202416/results?session=X")).status_code == 422


async def test_laps_paginate_with_keyset_cursor_and_filter(client):
    """GET /events/{id}/laps pages by (driver, lap) and filters by driver.

    Why: SPEC requires paginated lists to keep responses small on the free API.
    """
    p1 = (await client.get("/events/202416/laps?limit=4")).json()
    assert len(p1["items"]) == 4 and p1["next_cursor"] == "leclerc:4"
    p2 = (await client.get(f"/events/202416/laps?limit=4&cursor={p1['next_cursor']}")).json()
    assert p2["items"][0]["driver_id"] == "leclerc" and p2["items"][0]["lap"] == 5
    rest = (await client.get("/events/202416/laps?limit=100&cursor=leclerc:5")).json()
    assert len(rest["items"]) == 5 and rest["next_cursor"] is None
    only = (await client.get("/events/202416/laps?drivers=norris")).json()
    assert {lap["driver_id"] for lap in only["items"]} == {"norris"}
    assert only["items"][1]["pit_in"] is True and only["items"][2]["pit_out"] is True


async def test_laps_validation(client):
    """Bad limits, sessions and cursors are rejected with 422.

    Why: the cursor is user-supplied via shareable URLs.
    """
    assert (await client.get("/events/202416/laps?limit=0")).status_code == 422
    assert (await client.get("/events/202416/laps?limit=5000")).status_code == 422
    assert (await client.get("/events/202416/laps?session=Q")).status_code == 422
    assert (await client.get("/events/202416/laps?cursor=nonsense")).status_code == 422


async def test_stints_return_strategy_in_finishing_order(client):
    """GET /events/{id}/stints returns stints, total laps and drivers in finishing order.

    Why: the tire strategy timeline renders rows top-to-bottom in finishing order.
    """
    s = (await client.get("/events/202416/stints")).json()
    assert s["total_laps"] == 5
    assert [d["id"] for d in s["drivers"]] == ["leclerc", "norris"]
    assert s["finish_position"] == {"leclerc": 1, "norris": 3}
    assert [(x["compound"], x["start_lap"], x["end_lap"]) for x in s["stints"][:2]] == [
        ("MEDIUM", 1, 2),
        ("HARD", 3, 5),
    ]


async def test_stints_empty_for_session_without_data(client):
    """A sprint request on a conventional weekend returns an empty strategy.

    Why: the UI shows an empty state rather than an error.
    """
    s = (await client.get("/events/202416/stints?session=S")).json()
    assert s["stints"] == [] and s["drivers"] == [] and s["total_laps"] == 0


async def test_traces_by_driver_code(client):
    """GET /events/{id}/traces?drivers=NOR,LEC returns columnar traces in request order.

    Why: the telemetry comparison URL uses driver codes, and order sets series colors.
    """
    r = await client.get("/events/202416/traces?drivers=nor,LEC&session=Q")
    assert r.status_code == 200
    t = r.json()
    assert t["circuit_id"] == "monza"
    assert [x["driver"]["code"] for x in t["traces"]] == ["NOR", "LEC"]
    assert t["traces"][0]["points"]["speed"] == [300, 310, 320]


async def test_traces_validation_and_unknown_codes(client):
    """Traces need 1-3 driver codes; unknown codes are ignored, not errors.

    Why: caps response size (bandwidth budget) while keeping old shared URLs working.
    """
    assert (await client.get("/events/202416/traces")).status_code == 422
    assert (await client.get("/events/202416/traces?drivers=")).status_code == 422
    four = "/events/202416/traces?drivers=VER,NOR,LEC,PIA"
    assert (await client.get(four)).status_code == 422
    t = (await client.get("/events/202416/traces?drivers=VER")).json()
    assert t["traces"] == []
    r = (await client.get("/events/202416/traces?drivers=NOR&session=R")).json()
    assert r["traces"] == []

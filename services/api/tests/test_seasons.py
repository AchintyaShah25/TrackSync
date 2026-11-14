import pytest

pytestmark = pytest.mark.db


async def test_list_seasons_counts_events_and_completed(client):
    """GET /seasons lists seasons newest first with event and completed counts.

    Why: the season picker and landing page rely on these counts.
    """
    r = await client.get("/seasons")
    assert r.status_code == 200
    data = r.json()
    assert [s["year"] for s in data] == [2024, 2023]
    assert data[0] == {"year": 2024, "events": 2, "completed": 1}
    assert r.headers["cache-control"].startswith("public")


async def test_list_events_includes_has_data_and_sessions(client):
    """GET /seasons/{y}/events returns rounds in order with sessions and has_data.

    Why: the season page links only events that have data; the countdown reads sessions.
    """
    r = await client.get("/seasons/2024/events")
    assert r.status_code == 200
    events = r.json()
    assert [e["round"] for e in events] == [16, 22]
    assert events[0]["has_data"] is True and events[1]["has_data"] is False
    assert events[0]["circuit_name"].startswith("Autodromo")
    assert [s["code"] for s in events[0]["sessions"]] == ["Q", "R"]


async def test_list_events_empty_season_and_unknown_season(client):
    """A season with no events returns []; an unknown season is 404; a silly year is 422.

    Why: distinguishes 'nothing yet' from 'does not exist' for the UI's empty states.
    """
    assert (await client.get("/seasons/2023/events")).json() == []
    assert (await client.get("/seasons/2030/events")).status_code == 404
    assert (await client.get("/seasons/1800/events")).status_code == 422

import pytest

pytestmark = pytest.mark.db


async def test_standings_for_season(client):
    """GET /standings/{y} returns driver and constructor standings with team colors.

    Why: the season page shows both tables, colored by team.
    """
    r = await client.get("/standings/2024")
    assert r.status_code == 200
    s = r.json()
    assert s["after_round"] == 16
    assert [d["driver"]["code"] for d in s["drivers"]] == ["NOR", "LEC"]
    assert s["drivers"][0]["driver"]["team_id"] == "mclaren"
    assert s["constructors"][0] == {
        "position": 1,
        "team_id": "mclaren",
        "team_name": "McLaren",
        "color_hex": "#FF8000",
        "points": 200.0,
        "wins": 3,
    }


async def test_standings_missing_season_is_404(client):
    """A season without a standings snapshot is 404.

    Why: lets the UI show 'standings not available yet'.
    """
    assert (await client.get("/standings/2023")).status_code == 404
    assert (await client.get("/standings/99")).status_code == 422

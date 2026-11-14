import pytest

pytestmark = pytest.mark.db


async def test_circuit_with_outline_and_corners(client):
    """GET /circuits/{id} returns the normalized outline and corner markers.

    Why: the track map draws exactly these coordinates.
    """
    c = (await client.get("/circuits/monza")).json()
    assert c["length_m"] == 5755
    assert c["outline"]["x"] == [0, 1, 1, 0]
    assert c["corners"][0]["number"] == 1


async def test_circuit_without_outline_and_unknown_circuit(client):
    """A circuit with no outline yet returns outline null and no corners; unknown is 404.

    Why: future circuits exist in the schedule before any data is ingested.
    """
    c = (await client.get("/circuits/las_vegas")).json()
    assert c["outline"] is None and c["corners"] == []
    assert (await client.get("/circuits/nowhere")).status_code == 404

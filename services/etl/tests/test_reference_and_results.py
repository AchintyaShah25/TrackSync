from datetime import UTC, datetime

from pitwall_etl.transform import reference, results
from pitwall_etl.transform.common import event_id, slugify


def test_event_rows_from_recorded_schedule(fixture_frame):
    """Schedule rows become events with deterministic ids, slugs and UTC session times.

    Why: event ids are the idempotency key for every event-scoped table, and the landing
    page countdown reads race_start_utc.
    """
    circuits, events = reference.event_rows(
        2024, fixture_frame("jolpica_schedule_2024_r15-17.json")
    )
    monza = next(e for e in events if e["round"] == 16)
    assert monza["id"] == 202416
    assert monza["circuit_id"] == "monza"
    assert monza["slug"] == "italian-grand-prix"
    assert monza["format"] == "conventional"
    assert monza["race_start_utc"] == datetime(2024, 9, 1, 13, 0, tzinfo=UTC)
    assert [s["code"] for s in monza["sessions"]] == ["FP1", "FP2", "FP3", "Q", "R"]
    assert {c["id"] for c in circuits} >= {"monza", "zandvoort"}


def test_is_completed_uses_race_start_plus_margin():
    """An event counts as finished only a few hours after lights out.

    Why: ingesting a race that is still running would store partial laps.
    """
    event = {"race_start_utc": datetime(2024, 9, 1, 13, tzinfo=UTC)}
    assert not reference.is_completed(event, now=datetime(2024, 9, 1, 15, tzinfo=UTC))
    assert reference.is_completed(event, now=datetime(2024, 9, 1, 18, tzinfo=UTC))


def test_race_results_use_total_time_and_jolpica_ids(fixture_frame):
    """Race results carry Jolpica ids, total race time in ms, and map raced numbers.

    Why: Jolpica ids are our stable driver/team keys, and number_to_driver is how OpenF1
    rows (keyed by car number) are joined to them.
    """
    bundle = results.ResultBundle()
    results.add_race_like(
        bundle, 202416, 2024, "R", fixture_frame("jolpica_race_2024_16_top4.json")
    )
    first = bundle.results[0]
    assert first["driver_id"] == "leclerc" and first["team_id"] == "ferrari"
    assert first["position"] == 1 and first["points"] == 25.0
    assert first["time_ms"] == 4480727  # total time, not the gap FastF1 sessions report
    assert bundle.number_to_driver[16] == "leclerc"
    assert ("leclerc", 2024, "ferrari") in bundle.driver_teams


def test_qualifying_time_is_best_of_q1_q3(fixture_frame):
    """Qualifying time_ms is the driver's best lap across Q1, Q2 and Q3.

    Why: the results table shows one qualifying time per driver.
    """
    df = fixture_frame("jolpica_quali_2024_16_top4.json")
    bundle = results.ResultBundle()
    results.add_qualifying(bundle, 202416, 2024, df)
    row = df.iloc[0]
    best = min(t for t in (row["Q1"], row["Q2"], row["Q3"]) if t == t)
    assert bundle.results[0]["time_ms"] == int(best.total_seconds() * 1000)


def test_team_colors_come_from_openf1_via_driver_number(fixture_frame, fixture_json):
    """Team colors are filled from OpenF1 team_colour as #RRGGBB through driver numbers.

    Why: charts color driver series by team; a missing color falls back to a neutral gray.
    """
    bundle = results.ResultBundle()
    results.add_race_like(
        bundle, 202416, 2024, "R", fixture_frame("jolpica_race_2024_16_top4.json")
    )
    results.apply_team_colors(bundle, fixture_json("openf1_drivers_9590.json"))
    colored = [t for t in bundle.teams.values() if t["color_hex"]]
    assert colored and all(
        t["color_hex"].startswith("#") and len(t["color_hex"]) == 7 for t in colored
    )


def test_unclassified_position_is_null():
    """A retired driver ('R' positionText) has no classified position.

    Why: standings and result tables must not show a DNF as P17.
    """
    import pandas as pd

    row = pd.Series({"positionText": "R", "position": 17})
    assert results._classified_position(row) is None


def test_ids_and_slugs_are_deterministic():
    """event_id and slugify are pure and stable.

    Why: re-running the ETL must produce identical keys (idempotency acceptance criterion).
    """
    assert event_id(2024, 16) == 202416
    assert slugify("São Paulo Grand Prix") == "sao-paulo-grand-prix"

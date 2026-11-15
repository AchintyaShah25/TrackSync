from datetime import UTC, datetime, timedelta

from tracksync_etl.transform.laps import build_laps, build_stints, lap_status, status_windows

T0 = datetime(2024, 11, 3, 15, 30, tzinfo=UTC)


def at(seconds: float) -> str:
    return (T0 + timedelta(seconds=seconds)).isoformat()


def rc(seconds, category, message, flag=None, scope=None):
    return {
        "date": at(seconds),
        "category": category,
        "message": message,
        "flag": flag,
        "scope": scope,
    }


def test_status_windows_cover_vsc_sc_and_red_flag():
    """SC, VSC and red-flag periods become time windows with FastF1 status codes.

    Why: Milestone 2 excludes neutralized laps from tire-degradation fitting; a wrong
    window would leak SC laps (much slower) into the fit.
    """
    msgs = [
        rc(100, "SafetyCar", "VIRTUAL SAFETY CAR DEPLOYED"),
        rc(160, "SafetyCar", "VIRTUAL SAFETY CAR ENDING"),
        rc(300, "SafetyCar", "SAFETY CAR DEPLOYED"),
        rc(500, "Flag", "RED FLAG", flag="RED", scope="Track"),
        rc(900, "Flag", "GREEN LIGHT - PIT EXIT OPEN", flag="GREEN", scope="Track"),
    ]
    windows = status_windows(msgs, session_end=T0 + timedelta(hours=2))
    codes = {(w.code, (w.start - T0).seconds, (w.end - T0).seconds) for w in windows}
    assert ("6", 100, 160) in codes
    assert ("7", 160, 175) in codes
    assert ("4", 300, 500) in codes  # red flag closes the SC period
    assert ("5", 500, 900) in codes


def test_sc_window_extends_one_lap_past_in_this_lap():
    """'SAFETY CAR IN THIS LAP' keeps the lap it was shown on neutralized.

    Why: the SC peels off at the end of that lap, so the lap is still slow.
    """
    msgs = [
        rc(0, "SafetyCar", "SAFETY CAR DEPLOYED"),
        rc(200, "SafetyCar", "SAFETY CAR IN THIS LAP"),
    ]
    windows = status_windows(msgs, session_end=T0 + timedelta(hours=2))
    assert lap_status(windows, T0 + timedelta(seconds=250), T0 + timedelta(seconds=330)) == "4"
    assert lap_status(windows, T0 + timedelta(seconds=400), T0 + timedelta(seconds=480)) == "1"


def test_red_flag_ends_when_race_resumes_behind_safety_car():
    """A red flag closes at the SC restart when no track-wide GREEN flag follows.

    Why: Brazil 2024 restarted behind the SC with no GREEN message, and the first
    version marked every lap after the red flag as red (found in real-data validation).
    """
    msgs = [
        rc(0, "SafetyCar", "SAFETY CAR DEPLOYED"),
        rc(270, "Flag", "RED FLAG", flag="RED", scope="Track"),
        rc(2400, "SafetyCar", "SAFETY CAR DEPLOYED"),
        rc(2700, "SafetyCar", "SAFETY CAR IN THIS LAP"),
    ]
    windows = status_windows(msgs, session_end=T0 + timedelta(hours=3))
    codes = sorted((w.code, (w.start - T0).seconds, (w.end - T0).seconds) for w in windows)
    assert codes == [("4", 0, 270), ("4", 2400, 2850), ("5", 270, 2400)]
    late = lap_status(windows, T0 + timedelta(seconds=3000), T0 + timedelta(seconds=3080))
    assert late == "1"


def test_unterminated_window_runs_to_session_end():
    """A status still open when messages stop lasts until the session ends.

    Why: races can finish under SC; those final laps must still be flagged.
    """
    end = T0 + timedelta(hours=2)
    windows = status_windows([rc(10, "SafetyCar", "SAFETY CAR DEPLOYED")], session_end=end)
    assert windows[0].end == end


def _lap(num, n, start, duration, pit_out=False):
    return {
        "driver_number": num,
        "lap_number": n,
        "date_start": at(start),
        "lap_duration": duration,
        "is_pit_out_lap": pit_out,
    }


def test_build_laps_derives_pit_flags_tyre_life_position_and_accuracy():
    """Laps get in/out flags, compound, tyre age, position and is_accurate from OpenF1 feeds.

    Why: these derived fields are what the strategy timeline and Milestone 2's fitting
    rely on; OpenF1 does not provide them per lap directly.
    """
    laps = [
        _lap(16, 1, 0, 90),
        _lap(16, 2, 90, 85),
        _lap(16, 3, 175, 95),
        _lap(16, 4, 270, 100, True),
        _lap(16, 5, 370, 84),
    ]
    stints = [
        {
            "driver_number": 16,
            "stint_number": 1,
            "lap_start": 1,
            "lap_end": 3,
            "compound": "MEDIUM",
            "tyre_age_at_start": 2,
        },
        {
            "driver_number": 16,
            "stint_number": 2,
            "lap_start": 4,
            "lap_end": 5,
            "compound": "HARD",
            "tyre_age_at_start": 0,
        },
    ]
    pits = [{"driver_number": 16, "lap_number": 3}]
    positions = [
        {"driver_number": 16, "date": at(0), "position": 4},
        {"driver_number": 16, "date": at(200), "position": 2},
    ]
    rows = build_laps(
        event_id=202416,
        session="R",
        laps=laps,
        stints=stints,
        pits=pits,
        positions=positions,
        race_control=[],
        session_end=T0 + timedelta(hours=2),
        number_to_driver={16: "leclerc"},
    )
    by_lap = {r["lap"]: r for r in rows}
    assert by_lap[1]["is_accurate"] is False  # lap 1 excluded
    assert by_lap[2]["is_accurate"] is True and by_lap[2]["lap_time_ms"] == 85000
    assert by_lap[3]["pit_in"] is True and by_lap[3]["is_accurate"] is False
    assert by_lap[4]["pit_out"] is True and by_lap[4]["compound"] == "HARD"
    assert by_lap[1]["tyre_life"] == 3 and by_lap[3]["tyre_life"] == 5
    assert by_lap[1]["position"] == 4 and by_lap[3]["position"] == 2
    assert all(r["track_status"] == "1" for r in rows)


def test_build_laps_skips_drivers_unknown_to_jolpica():
    """OpenF1 rows whose driver number is not in the official results are dropped.

    Why: every lap row needs a valid drivers.id foreign key.
    """
    rows = build_laps(
        event_id=1,
        session="R",
        laps=[_lap(99, 1, 0, 90)],
        stints=[],
        pits=[],
        positions=[],
        race_control=[],
        session_end=T0,
        number_to_driver={},
    )
    assert rows == []


def test_build_stints_dedupes_repeated_stint_numbers():
    """A stint number OpenF1 repeats is stored once (last wins).

    Why: (event, session, driver, stint) is the primary key; duplicates would abort the load.
    """
    stints = [
        {"driver_number": 1, "stint_number": 1, "lap_start": 1, "lap_end": 10, "compound": "SOFT"},
        {"driver_number": 1, "stint_number": 1, "lap_start": 1, "lap_end": 12, "compound": "SOFT"},
    ]
    rows = build_stints(
        event_id=1, session="R", stints=stints, number_to_driver={1: "max_verstappen"}
    )
    assert len(rows) == 1 and rows[0]["end_lap"] == 12


def test_build_stints_drops_stints_ending_before_they_start():
    """OpenF1 stints like laps 1-0 (car retired before completing a lap) are dropped.

    Why: Australia 2023 had several such rows; the end_lap >= start_lap check constraint
    rejected the whole event and aborted the season backfill (seen 2026-11-14).
    """
    stints = [
        {"driver_number": 31, "stint_number": 1, "lap_start": 1, "lap_end": 0, "compound": "SOFT"},
        {"driver_number": 1, "stint_number": 1, "lap_start": 1, "lap_end": 30, "compound": "HARD"},
    ]
    rows = build_stints(
        event_id=202303,
        session="R",
        stints=stints,
        number_to_driver={31: "ocon", 1: "max_verstappen"},
    )
    assert [r["driver_id"] for r in rows] == ["max_verstappen"]

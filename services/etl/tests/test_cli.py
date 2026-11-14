from datetime import UTC, datetime

from pitwall_etl import cli
from pitwall_etl.pipeline import EventReport


class FakeStore:
    def __init__(self):
        self.finished = None

    def start_run(self, args):
        return 1

    def finish_run(self, run_id, status, counts, error=None):
        self.finished = (status, counts, error)


def _event(rnd):
    return {
        "id": 202300 + rnd,
        "season": 2023,
        "round": rnd,
        "race_start_utc": datetime(2023, 3, rnd, tzinfo=UTC),
    }


def test_one_failing_event_does_not_abort_the_season(monkeypatch):
    """An exception in one event is recorded and the remaining events still run.

    Why: a single malformed source row must not stop a multi-hour backfill; the run
    still exits non-zero so CI shows the failure.
    """
    store = FakeStore()
    ingested = []

    class FakePipeline:
        def __init__(self, *a, **k):
            pass

        def ingest_schedule(self, season):
            return [_event(1), _event(2), _event(3)]

        def ingest_event(self, event):
            if event["round"] == 2:
                raise ValueError("bad row")
            ingested.append(event["round"])
            return EventReport(event["id"])

        def ingest_standings(self, season):
            return 0

    monkeypatch.setattr(cli, "configure_fastf1", lambda path: None)
    monkeypatch.setattr(cli, "make_engine", lambda url: None)
    monkeypatch.setattr(cli, "Store", lambda engine: store)
    monkeypatch.setattr(cli, "Pipeline", FakePipeline)
    monkeypatch.setattr(cli, "select_events", lambda events, args, st, now: events)

    assert cli.main(["--season", "2023"]) == 1
    assert ingested == [1, 3]
    status, counts, error = store.finished
    assert status == "failed"
    assert "202302" in counts["failed_events"] and "bad row" in counts["failed_events"]["202302"]
    assert "202302" in error

from datetime import UTC, datetime

from tracksync_etl import cli
from tracksync_etl.pipeline import EventReport


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


def _fake_pipeline(loaded_laps: int):
    class FakePipeline:
        def __init__(self, *a, **k):
            pass

        def ingest_schedule(self, season):
            return [_event(1)]

        def ingest_event(self, event):
            report = EventReport(event["id"])
            report.counts["laps"] = loaded_laps
            return report

        def ingest_standings(self, season):
            return 0

    return FakePipeline


def _patch(monkeypatch, store, pipeline, refits):
    monkeypatch.setattr(cli, "configure_fastf1", lambda path: None)
    monkeypatch.setattr(cli, "make_engine", lambda url: None)
    monkeypatch.setattr(cli, "Store", lambda engine: store)
    monkeypatch.setattr(cli, "Pipeline", pipeline)
    monkeypatch.setattr(cli, "select_events", lambda events, args, st, now: events)
    monkeypatch.setattr(cli.fit_models, "refit_all", lambda st: refits.append(st) or 26)


def test_fit_models_alone_skips_ingestion(monkeypatch):
    """`--fit-models` without a season refits the model and ingests nothing.

    Why: after a model change we refit production without re-downloading any data.
    """
    store, refits = FakeStore(), []

    class NoIngest:
        def __init__(self, *a, **k):
            pass

        def ingest_schedule(self, season):
            raise AssertionError("must not ingest")

    _patch(monkeypatch, store, NoIngest, refits)
    assert cli.main(["--fit-models"]) == 0
    assert refits == [store]
    assert store.finished[0] == "ok" and store.finished[1]["model_params"] == 26


def test_a_run_that_loads_laps_refits_the_model(monkeypatch):
    """Loading any event's laps triggers a refit at the end of the run.

    Why: the weekly cron must keep the model current without a second job.
    """
    store, refits = FakeStore(), []
    _patch(monkeypatch, store, _fake_pipeline(loaded_laps=900), refits)
    assert cli.main(["--season", "2023"]) == 0
    assert refits == [store]


def test_a_run_that_loads_nothing_does_not_refit(monkeypatch):
    """No new laps, no refit.

    Why: a scheduled run in a week without a race should stay cheap.
    """
    store, refits = FakeStore(), []
    _patch(monkeypatch, store, _fake_pipeline(loaded_laps=0), refits)
    assert cli.main(["--season", "2023"]) == 0
    assert refits == []


def test_a_failed_refit_fails_the_run(monkeypatch):
    """If fitting raises, the loaded data stays and the run exits non-zero.

    Why: a stale model must be noticed (red CI job), but must not roll back the load.
    """
    store, refits = FakeStore(), []
    _patch(monkeypatch, store, _fake_pipeline(loaded_laps=900), refits)

    def boom(st):
        raise RuntimeError("singular matrix")

    monkeypatch.setattr(cli.fit_models, "refit_all", boom)
    assert cli.main(["--season", "2023"]) == 1
    status, counts, error = store.finished
    assert status == "failed" and "singular matrix" in counts["model_fit_error"]
    assert counts["failed_events"] == {} and "model fit failed" in error


def test_fit_models_cannot_be_a_dry_run():
    """`--fit-models --dry-run` is rejected at argument parsing.

    Why: fitting writes to the database; a dry run promising no writes must not.
    """
    import pytest

    with pytest.raises(SystemExit):
        cli.parse_args(["--fit-models", "--dry-run"])

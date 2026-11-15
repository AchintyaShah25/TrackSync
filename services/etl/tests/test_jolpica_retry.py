import pytest
import requests
from tracksync_etl.sources.jolpica import retry_transient


def test_retries_dropped_connections_then_succeeds():
    """A dropped connection is retried with backoff and the call then succeeds.

    Why: a single RemoteDisconnected from Jolpica failed Zandvoort 2024 in the backfill.
    """
    calls, sleeps = [], []

    @retry_transient(attempts=3, base_delay=1, sleep=sleeps.append)
    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise requests.ConnectionError("Remote end closed connection")
        return "ok"

    assert flaky() == "ok"
    assert sleeps == [1, 2]


def test_gives_up_after_attempts_and_does_not_retry_other_errors():
    """Persistent outages still fail; non-network errors are not retried.

    Why: a real outage must surface (the event is then recorded as failed), and a bug
    such as a KeyError must not be hidden behind retries.
    """
    sleeps = []

    @retry_transient(attempts=2, base_delay=1, sleep=sleeps.append)
    def down():
        raise requests.Timeout("timed out")

    with pytest.raises(requests.Timeout):
        down()
    assert sleeps == [1]

    @retry_transient(attempts=3, base_delay=1, sleep=sleeps.append)
    def bug():
        raise KeyError("x")

    with pytest.raises(KeyError):
        bug()
    assert sleeps == [1]


def test_rate_limit_waits_a_full_minute_then_succeeds():
    """A Jolpica 429 (surfaced by FastF1 as ErgastInvalidRequestError) waits ~60 s and retries.

    Why: the 2024 re-run hit 'Too Many Requests' on Zandvoort; the generic invalid-request
    error must still not be retried for real bad requests.
    """
    from fastf1.exceptions import ErgastInvalidRequestError

    sleeps, calls = [], []

    @retry_transient(attempts=3, base_delay=1, sleep=sleeps.append)
    def limited():
        calls.append(1)
        if len(calls) == 1:
            raise ErgastInvalidRequestError("Invalid request\nServer response: 'Too Many Requests'")
        return "ok"

    assert limited() == "ok"
    assert sleeps == [60.0]

    @retry_transient(attempts=3, base_delay=1, sleep=sleeps.append)
    def bad_request():
        raise ErgastInvalidRequestError("Invalid request\nServer response: 'Bad Request'")

    with pytest.raises(ErgastInvalidRequestError):
        bad_request()
    assert sleeps == [60.0]

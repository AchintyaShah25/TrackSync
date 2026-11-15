import json

import pytest
from tracksync_etl.sources.openf1 import OpenF1Client, OpenF1Error, RateLimiter


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.slept = 0.0

    def clock(self):
        return self.now

    def sleep(self, s):
        self.now += s
        self.slept += s


def test_rate_limiter_respects_per_minute_cap():
    """The 29th call inside a minute waits until the window frees up.

    Why: OpenF1's free tier allows 30 req/min; exceeding it gets 429s and slows backfills.
    """
    c = FakeClock()
    rl = RateLimiter(per_minute=28, per_second=100, clock=c.clock, sleep=c.sleep)
    for _ in range(28):
        rl.wait()
    assert c.slept == 0
    rl.wait()
    assert c.slept >= 59.9


def test_rate_limiter_respects_per_second_cap():
    """No more than 3 calls start within one second.

    Why: OpenF1 also caps bursts at 3 req/s.
    """
    c = FakeClock()
    rl = RateLimiter(per_minute=100, per_second=3, clock=c.clock, sleep=c.sleep)
    for _ in range(4):
        rl.wait()
    assert c.slept >= 0.99


def test_build_url_keeps_operator_keys_unescaped():
    """Filter operators like date> stay literal in the query string.

    Why: OpenF1 parses 'date>2024-...' itself; URL-escaping '>' silently drops the filter
    and returns a whole session of telemetry.
    """
    url = OpenF1Client.build_url("car_data", {"session_key": 9590, "date>": "2024-09-01T13:40:00"})
    assert url == "https://api.openf1.org/v1/car_data?session_key=9590&date>2024-09-01T13:40:00"


class FakeResponse:
    def __init__(self, status, data):
        self.status_code, self._data = status, data
        self.ok = 200 <= status < 300
        self.headers = {}
        self.text = json.dumps(data)

    def json(self):
        return self._data


class FakeHttp:
    def __init__(self, responses):
        self.responses = list(responses)
        self.headers = {}
        self.calls = 0

    def get(self, url, timeout):
        self.calls += 1
        return self.responses.pop(0)


def test_get_caches_responses_on_disk(tmp_path):
    """A cached URL is served from disk without a second request.

    Why: the cache makes ETL re-runs and resumed backfills free of API calls.
    """
    http = FakeHttp([FakeResponse(200, [{"a": 1}])])
    client = OpenF1Client(tmp_path, session=http)
    assert client.get("laps", session_key=1) == [{"a": 1}]
    assert client.get("laps", session_key=1) == [{"a": 1}]
    assert http.calls == 1


def test_get_treats_404_as_empty_and_raises_on_other_client_errors(tmp_path, monkeypatch):
    """404 ('No results found') means no data; other 4xx errors fail loudly.

    Why: missing data is normal (e.g. no SC messages); a bad request is a bug.
    """
    client = OpenF1Client(tmp_path, session=FakeHttp([FakeResponse(404, {"detail": "No results"})]))
    assert client.get("race_control", session_key=1) == []
    client = OpenF1Client(None, session=FakeHttp([FakeResponse(422, {"detail": "bad"})]))
    with pytest.raises(OpenF1Error):
        client.get("laps", session_key=1)


def test_get_retries_on_429_after_a_full_window(tmp_path, monkeypatch):
    """A 429 is retried after waiting out a full rate-limit window instead of failing.

    Why: the per-minute quota can be spent by an earlier run the local limiter cannot
    see; short exponential backoff gave up before the window reset (seen 2026-11-14).
    """
    sleeps = []
    monkeypatch.setattr("tracksync_etl.sources.openf1.time.sleep", sleeps.append)
    http = FakeHttp([FakeResponse(429, {}), FakeResponse(200, [{"ok": True}])])
    client = OpenF1Client(None, session=http)
    assert client.get("laps", session_key=1) == [{"ok": True}]
    assert http.calls == 2
    assert sleeps == [61]

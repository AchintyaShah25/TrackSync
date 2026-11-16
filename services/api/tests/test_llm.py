"""LLM client and fallback chain with scripted fake transports (no network)."""

import json

import pytest
from app.config import Settings
from app.llm import AllProvidersDown, LLMChain, OpenAICompatClient, Provider, build_chain
from app.llm.client import BadResponse, RateLimited, Unavailable
from app.llm.embed import EMBED_DIM, embed_query


def ok(content="hi", tool_calls=None):
    msg = {"role": "assistant", "content": content}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return (
        200,
        {},
        json.dumps({"choices": [{"message": msg}], "usage": {"total_tokens": 9}}).encode(),
    )


class Script:
    """Fake transport: returns queued responses (or raises) and records requests."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, headers, body, timeout):
        self.calls.append((url, headers, json.loads(body), timeout))
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def client(name, script):
    return OpenAICompatClient(
        Provider(name, f"https://{name}.test/v1", "key-" + name, name + "-m"), script
    )


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


async def test_client_sends_openai_request_and_parses_message():
    """The request is OpenAI-compatible (model, messages, tools) with a bearer key.

    Why: Groq and Gemini share this wire format; a wrong field silently disables tools.
    """
    s = Script(
        ok(
            tool_calls=[
                {"id": "1", "type": "function", "function": {"name": "f", "arguments": "{}"}}
            ]
        )
    )
    res = await client("groq", s).chat(
        [{"role": "user", "content": "q"}], tools=[{"type": "function"}]
    )
    url, headers, body, _ = s.calls[0]
    assert url == "https://groq.test/v1/chat/completions"
    assert headers["Authorization"] == "Bearer key-groq"
    assert body["model"] == "groq-m" and body["tool_choice"] == "auto"
    assert res.message["tool_calls"][0]["function"]["name"] == "f" and res.provider == "groq"


@pytest.mark.parametrize(
    ("response", "error"),
    [
        ((429, {"Retry-After": "12"}, b"slow down"), RateLimited),
        ((503, {}, b"down"), Unavailable),
        ((401, {}, b"bad key"), Unavailable),
        ((400, {}, b"bad request"), BadResponse),
        ((200, {}, b"not json"), BadResponse),
        (Unavailable("timeout"), Unavailable),
    ],
)
async def test_client_maps_failures_to_typed_errors(response, error):
    """Each failure mode becomes a typed error the chain knows how to handle.

    Why: the chain falls back on 429/5xx but must not bench a provider for one odd reply.
    """
    with pytest.raises(error):
        await client("groq", Script(response)).chat([{"role": "user", "content": "q"}])


async def test_chain_falls_back_and_cools_down_a_rate_limited_provider():
    """A 429 from Groq answers via Gemini, and Groq is skipped until Retry-After passes.

    Why: free tiers rate-limit within minutes; users should still get an answer.
    """
    clock = Clock()
    groq = Script((429, {"retry-after": "20"}, b""), ok("from groq"))
    gemini = Script(ok("from gemini"), ok("gemini again"))
    chain = LLMChain([client("groq", groq), client("gemini", gemini)], clock=clock)
    assert (await chain.chat([])).provider == "gemini"
    clock.t += 5
    assert (await chain.chat([])).message["content"] == "gemini again"  # groq still cooling
    assert len(groq.calls) == 1
    clock.t += 30
    assert (await chain.chat([])).provider == "groq"  # cooldown over


async def test_chain_reports_all_down_with_a_retry_hint():
    """When every provider fails, the chain raises AllProvidersDown with the shortest wait.

    Why: the API turns this into a friendly 503 with Retry-After, not a stack trace.
    """
    chain = LLMChain(
        [
            client("groq", Script((429, {"retry-after": "40"}, b""))),
            client("gemini", Script((500, {}, b""))),
        ],
        clock=Clock(),
    )
    with pytest.raises(AllProvidersDown) as info:
        await chain.chat([])
    assert info.value.retry_after == pytest.approx(30.0)  # gemini's unavailable cooldown


async def test_bad_response_does_not_bench_the_provider():
    """A malformed reply falls through for this request only.

    Why: one odd response should not remove the primary provider for 30 seconds.
    """
    groq = Script((200, {}, b"{}"), ok("fine now"))
    chain = LLMChain([client("groq", groq), client("gemini", Script(ok("g")))], clock=Clock())
    assert (await chain.chat([])).provider == "gemini"
    assert (await chain.chat([])).provider == "groq"


def test_build_chain_skips_providers_without_keys():
    """Providers are built in LLM_CHAIN order, only when their API key is set.

    Why: local dev and CI run without keys; chat must report "not configured", not crash.
    """
    assert not build_chain(Settings(groq_api_key="", gemini_api_key="")).configured
    chain = build_chain(Settings(groq_api_key="g", gemini_api_key="m", llm_chain="gemini, groq"))
    assert [c.provider.name for c in chain.clients] == ["gemini", "groq"]
    only = build_chain(Settings(groq_api_key="", gemini_api_key="m"))
    assert [c.provider.name for c in only.clients] == ["gemini"]


def test_build_chain_accepts_several_models_per_provider():
    """ "provider:model" entries build one client per model; bare names use the default.

    Why: free quotas are per model (Groq: ~200k tokens a day each), so chaining several
    Groq models multiplies daily capacity (decision 0036).
    """
    chain = build_chain(
        Settings(
            groq_api_key="g",
            gemini_api_key="m",
            llm_chain="groq:big/model, groq:small/model ,gemini",
        )
    )
    assert [(c.provider.name, c.provider.model) for c in chain.clients] == [
        ("groq", "big/model"),
        ("groq", "small/model"),
        ("gemini", Settings().gemini_model),
    ]


async def test_rate_limit_benches_only_that_model():
    """A 429 on one model of a provider still lets the next model of the same provider answer,
    and the benched model is skipped until its cooldown ends.

    Why: on 2026-11-15 gpt-oss-120b hit its daily token cap; with per-provider cooldowns,
    every other Groq model would have been skipped too.
    """
    big = Script((429, {"retry-after": "60"}, b"{}"), ok("big again"))
    small = Script(ok("small"), ok("small 2"))
    mk = lambda m, sc: OpenAICompatClient(Provider("groq", "https://g.test/v1", "k", m), sc)  # noqa: E731
    clock = Clock()
    chain = LLMChain([mk("big", big), mk("small", small)], clock=clock)
    assert (await chain.chat([])).model == "small"
    assert (await chain.chat([])).model == "small"  # big still benched
    clock.t += 61
    assert (await chain.chat([])).model == "big"


async def test_embed_query_normalizes_and_degrades_to_none():
    """Embeddings come back unit-length; any failure returns None (full-text fallback).

    Why: 768-dim truncated Gemini vectors must be renormalized for cosine search, and an
    embedding outage must not break chat.
    """
    values = [3.0, 4.0] + [0.0] * (EMBED_DIM - 2)
    good = Script((200, {}, json.dumps({"embedding": {"values": values}}).encode()))
    v = await embed_query("pit stop rules", "key", good)
    assert v[:2] == [pytest.approx(0.6), pytest.approx(0.8)]
    assert good.calls[0][2]["taskType"] == "RETRIEVAL_QUERY"
    assert await embed_query("q", "key", Script((429, {}, b""))) is None
    assert await embed_query("q", "key", Script(Unavailable("timeout"))) is None
    assert await embed_query("q", "", Script()) is None  # no key: no call


def test_urllib_transport_names_a_client_instead_of_python_urllib(monkeypatch):
    """Requests carry our generic User-Agent, and a caller's headers are kept.

    Why: Groq's Cloudflare front answers urllib's default agent with 403 error 1010; on
    2026-11-15 that silently pushed every eval question onto the fallback provider.
    """
    from app.llm import client

    seen = {}

    class Resp:
        status = 200
        headers: dict = {}  # noqa: RUF012

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"{}"

    def fake_urlopen(req, timeout):
        seen.update(req.header_items())
        return Resp()

    monkeypatch.setattr(client.urllib.request, "urlopen", fake_urlopen)
    client.urllib_transport("https://llm.test/v1", {"Authorization": "Bearer k"}, b"{}", 5)
    assert seen["User-agent"] == client.USER_AGENT
    assert seen["Authorization"] == "Bearer k"

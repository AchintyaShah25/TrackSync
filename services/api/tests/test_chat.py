"""POST /chat with a scripted fake LLM (no network): tools, grounding, citations, limits."""

import json

import httpx
import psycopg
import pytest
from app.auth import AuthVerifier
from app.config import Settings
from app.llm import AllProvidersDown, ChatResult
from app.main import create_app

from .conftest import SEED

pytestmark = pytest.mark.db


@pytest.fixture(scope="module")
def chat_db(fresh_database) -> str:
    url = fresh_database("tracksync_test_chat")
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(SEED.read_text())
        doc = conn.execute(
            "insert into rag_documents (source, source_key, title, url, license, season, "
            "content_hash) values (%s, %s, %s, %s, %s, 2026, 'h') returning id",
            (
                "fia",
                "fia:sporting:2026",
                "2026 F1 Sporting Regulations",
                "https://fia.test/b.pdf",
                "© FIA",
            ),
        ).fetchone()[0]
        conn.execute(
            "insert into rag_chunks (document_id, ord, section, heading, content) "
            "values (%s, 0, %s, %s, %s)",
            (
                doc,
                "Article B5.13 Safety Car (SC)",
                "2026 F1 Sporting Regulations Article B5.13 Safety Car",
                "All cars must reduce speed and form up behind the safety car no more than "
                "ten car lengths apart.",
            ),
        )
    return url


def tools(*calls):
    return lambda m: {"role": "assistant", "content": "", "tool_calls": list(calls)}


def reply(text):
    return lambda m: {"role": "assistant", "content": text}


def call(name, args, id_="c1"):
    return {
        "id": id_,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(args)},
    }


class FakeLLM:
    """Plays a script: each step is a function(messages) -> assistant message dict."""

    configured = True

    def __init__(self, *steps):
        self.steps = list(steps)
        self.seen: list[list[dict]] = []

    async def chat(self, messages, tools=None, **kw):
        self.seen.append(json.loads(json.dumps(messages)))
        msg = self.steps.pop(0)(messages)
        return ChatResult(message=msg, provider="fake", model="fake-1")


def tool_outputs(messages):
    return [json.loads(m["content"]) for m in messages if m["role"] == "tool"]


async def make_client(url, llm, **settings):
    app = create_app(Settings(database_url=url, web_origin="http://localhost:3000", **settings))
    ctx = app.router.lifespan_context(app)
    await ctx.__aenter__()
    app.state.llm = llm
    app.state.embed_transport = lambda *a: (500, {}, b"")  # embeddings down: full-text only
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    return app, ctx, client


def ask(text, **kw):
    return {"messages": [{"role": "user", "content": text}], **kw}


async def test_stats_answers_come_from_query_stats(chat_db):
    """A stats question runs query_stats and the model sees real rows from our database.

    Why: SPEC M3 acceptance: "stats answers come from query_stats, not retrieval".
    """
    monza = {"season": 2024, "race": "Monza"}
    llm = FakeLLM(
        tools(call("query_stats", {"name": "race_result", "params": monza})),
        reply("Charles Leclerc won the 2024 Italian Grand Prix."),
    )
    _, ctx, c = await make_client(chat_db, llm)
    try:
        r = await c.post("/chat", json=ask("Who won at Monza in 2024?"))
    finally:
        await c.aclose()
        await ctx.__aexit__(None, None, None)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["tools_used"] == ["query_stats"] and body["provider"] == "fake"
    result = tool_outputs(llm.seen[1])[0]
    assert result["classification"][0]["driver"] == "Charles Leclerc"
    assert "query_stats" in llm.seen[0][0]["content"]  # the system prompt states the rule


async def test_citations_keep_only_real_passages(chat_db):
    """Retrieved passages are numbered; the answer's valid [n] become sources, dead ones vanish.

    Why: every citation the UI shows must open a real FIA/Wikipedia/summary passage.
    """
    llm = FakeLLM(
        tools(call("search_knowledge", {"query": "safety car deployed", "source": "fia"})),
        reply("Cars queue behind the safety car within ten car lengths [1]. Also [7]."),
    )
    _, ctx, c = await make_client(chat_db, llm)
    try:
        body = (await c.post("/chat", json=ask("What happens under a safety car?"))).json()
    finally:
        await c.aclose()
        await ctx.__aexit__(None, None, None)
    passages = tool_outputs(llm.seen[1])[0]["passages"]
    assert passages[0]["n"] == 1 and "ten car lengths" in passages[0]["text"]
    assert [s["n"] for s in body["sources"]] == [1]
    assert body["sources"][0]["license"] == "© FIA" and body["sources"][0]["section"].startswith(
        "Article B5.13"
    )
    assert "[1]" in body["answer"] and "[7]" not in body["answer"]


async def test_charts_only_use_registered_datasets(chat_db):
    """make_chart rejects names that no query produced, and renders real points for valid ones.

    Why: grounded charts (decision 0029); the model must not be able to plot invented numbers.
    """

    def chart_real(m):
        refs = tool_outputs(m)[1]["chartable"]
        return tools(call("make_chart", {"title": "2024 drivers", "datasets": refs}))(m)

    llm = FakeLLM(
        tools(
            call("make_chart", {"title": "Made up", "datasets": ["fake:data"]}, "a"),
            call("query_stats", {"name": "standings", "params": {"season": 2024}}, "b"),
        ),
        chart_real,
        reply("Here are the standings."),
    )
    _, ctx, c = await make_client(chat_db, llm)
    try:
        body = (await c.post("/chat", json=ask("Chart the 2024 standings"))).json()
    finally:
        await c.aclose()
        await ctx.__aexit__(None, None, None)
    first = tool_outputs(llm.seen[1])
    assert "unknown dataset" in first[0]["error"]
    assert len(body["charts"]) == 1 and body["charts"][0]["type"] == "bar"
    points = body["charts"][0]["series"][0]["points"]
    assert points and all(isinstance(p[1], float | int) for p in points)


async def test_bad_tool_calls_return_errors_to_the_model(chat_db):
    """Unknown queries, bad JSON and unknown races come back as errors the model can read.

    Why: the model must be able to recover instead of the request failing with a 500.
    """
    bad_json = {
        "id": "b",
        "type": "function",
        "function": {"name": "query_stats", "arguments": "{not json"},
    }
    narnia = {"season": 2024, "race": "Narnia"}
    llm = FakeLLM(
        tools(
            call("query_stats", {"name": "drop_table", "params": {}}, "a"),
            bad_json,
            call("query_stats", {"name": "race_result", "params": narnia}, "c"),
        ),
        reply("I could not find that."),
    )
    _, ctx, c = await make_client(chat_db, llm)
    try:
        r = await c.post("/chat", json=ask("??"))
    finally:
        await c.aclose()
        await ctx.__aexit__(None, None, None)
    assert r.status_code == 200
    errors = [o["error"] for o in tool_outputs(llm.seen[1])]
    assert "unknown query" in errors[0] and "valid JSON" in errors[1] and "Narnia" in errors[2]


async def test_tool_budget_forces_a_final_answer(chat_db):
    """After 4 rounds of tool calls the agent asks for an answer without tools.

    Why: free tiers allow few requests per minute; a looping model must not burn them all.
    """
    loop = tools(call("query_stats", {"name": "next_race"}))
    llm = FakeLLM(loop, loop, loop, loop, reply("Final."))
    _, ctx, c = await make_client(chat_db, llm)
    try:
        body = (await c.post("/chat", json=ask("loop"))).json()
    finally:
        await c.aclose()
        await ctx.__aexit__(None, None, None)
    assert body["answer"] == "Final." and len(llm.seen) == 5
    assert "Tool budget used" in llm.seen[4][-1]["content"]


async def test_guest_limits_per_minute_and_per_day(chat_db):
    """Guests get 429 after the per-minute burst, and after the daily cap with a sign-in hint.

    Why: demo mode must not let one visitor spend the site's free LLM quota.
    """
    answer = reply("ok")
    _, ctx, c = await make_client(
        chat_db, FakeLLM(*[answer] * 10), chat_guest_per_minute=2, chat_guest_per_day=100
    )
    try:
        codes = [(await c.post("/chat", json=ask("hi"))).status_code for _ in range(3)]
    finally:
        await c.aclose()
        await ctx.__aexit__(None, None, None)
    assert codes == [200, 200, 429]

    _, ctx, c = await make_client(
        chat_db, FakeLLM(*[answer] * 10), chat_guest_per_minute=100, chat_guest_per_day=1
    )
    headers = {"X-Forwarded-For": "198.51.100.42"}
    try:
        first = await c.post("/chat", json=ask("hi"), headers=headers)
        second = await c.post("/chat", json=ask("hi"), headers=headers)
    finally:
        await c.aclose()
        await ctx.__aexit__(None, None, None)
    assert first.status_code == 200 and second.status_code == 429
    assert (
        "sign in for more" in second.json()["detail"] and int(second.headers["retry-after"]) >= 60
    )


async def test_signed_in_users_get_their_own_limits_and_bad_tokens_401(chat_db):
    """A valid token uses the user bucket; an invalid one is 401, not silently a guest.

    Why: a stale session must prompt the browser to refresh instead of shrinking limits.
    """
    answer = reply("ok")
    app, ctx, c = await make_client(
        chat_db, FakeLLM(*[answer] * 5), chat_guest_per_minute=1, chat_user_per_minute=5
    )

    def auth_server(url, headers, timeout):
        good = headers["Authorization"] == "Bearer good"
        return (200, b'{"id": "11111111-1111-1111-1111-111111111111"}') if good else (401, b"{}")

    app.state.auth = AuthVerifier("https://auth.test", "anon", transport=auth_server)
    try:
        user = [
            (
                await c.post("/chat", json=ask("hi"), headers={"Authorization": "Bearer good"})
            ).status_code
            for _ in range(3)
        ]
        bad = await c.post("/chat", json=ask("hi"), headers={"Authorization": "Bearer stale"})
    finally:
        await c.aclose()
        await ctx.__aexit__(None, None, None)
    assert user == [200, 200, 200]  # beyond the guest limit of 1
    assert bad.status_code == 401


async def test_unconfigured_or_busy_llm_is_a_friendly_503(chat_db):
    """No provider keys: 503 "not configured". All providers busy: 503 with Retry-After.

    Why: chat must fail gracefully; the rest of the site keeps working without LLM keys.
    """

    class Unconfigured:
        configured = False

    class Busy:
        configured = True

        async def chat(self, *a, **k):
            raise AllProvidersDown(retry_after=42)

    for llm, fragment in ((Unconfigured(), "not configured"), (Busy(), "busy")):
        _, ctx, c = await make_client(chat_db, llm)
        try:
            r = await c.post("/chat", json=ask("hi"))
        finally:
            await c.aclose()
            await ctx.__aexit__(None, None, None)
        assert r.status_code == 503 and fragment in r.json()["detail"]
    assert r.headers["retry-after"] == "42"


async def test_history_is_trimmed_and_starts_with_the_user(chat_db):
    """Only the last 12 messages go to the model, starting with a user message.

    Why: token budgets on free tiers are small; long browser histories must not blow them.
    """
    llm = FakeLLM(reply("ok"))
    history = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"} for i in range(21)
    ]
    _, ctx, c = await make_client(chat_db, llm)
    try:
        r = await c.post("/chat", json={"messages": history})
    finally:
        await c.aclose()
        await ctx.__aexit__(None, None, None)
    assert r.status_code == 200
    sent = [m for m in llm.seen[0] if m["role"] != "system"]
    assert len(sent) <= 12 and sent[0]["role"] == "user" and sent[-1]["content"] == "m20"

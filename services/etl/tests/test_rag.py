"""Knowledge base: parsing, chunking, summaries, embedding and idempotent storage."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import text
from tracksync_etl.load.db import make_engine
from tracksync_etl.rag import summaries
from tracksync_etl.rag.chunk import MAX_CHARS, OVERLAP, chunk_sections
from tracksync_etl.rag.embed import DIM, Embedder
from tracksync_etl.rag.load import store_documents
from tracksync_etl.rag.sources import (
    Document,
    latest_regulation_pdf,
    latest_sporting_pdf,
    regulation_sections,
    wikipedia_document,
    wikipedia_sections,
)

FIX = Path(__file__).parent / "fixtures" / "rag"


def test_latest_sporting_pdf_picks_newest_issue_for_the_season():
    """The FIA index lists many issues and next season's rules; we index this season's latest.

    Why: answers about "the rules" must reflect the issue in force, not a draft for 2027.
    """
    names = (
        "fia_2027_f1_regulations_-_section_b_sporting_-_iss_01_-_2026-10-19.pdf",
        "fia_2026_f1_regulations_-_section_b_sporting_-_iss_09_-_2026-10-01.pdf",
        "fia_2026_f1_regulations_-_section_b_sporting_-_iss03_-_2025-07-31.pdf",
        "fia_2026_f1_regulations_-_section_c_technical_-_iss_12_-_2026-10-01.pdf",
    )
    html = "".join(f'<a href="https://www.fia.com/files/{n}">x</a>' for n in names)
    assert latest_sporting_pdf(html, 2026).endswith("iss_09_-_2026-10-01.pdf")
    assert latest_sporting_pdf(html, 2025) is None
    general = (
        html
        + '<a href="https://www.fia.com/f/fia_2026_f1_regulations_-_section_a_general_provisions_-_iss_03_-_2026-06-25.pdf">'
    )
    # Section A holds the points system; it is indexed alongside Section B.
    assert "section_a_general_provisions_-_iss_03" in latest_regulation_pdf(general, 2026, "A")


def test_regulation_sections_split_real_pdf_pages_by_article():
    """Two real pages of the 2026 Sporting Regulations split into articles, headers removed.

    Why: citations name the article ("B5.13 Safety Car"); page headers in chunk text
    would pollute search.
    """
    sections = regulation_sections((FIX / "fia_sporting_2pages.pdf").read_bytes())
    labels = [label for label, _ in sections]
    assert any(label.startswith("Article B5.13 Safety Car") for label in labels)
    body = dict(sections)[next(lb for lb in labels if lb.startswith("Article B5.13"))]
    assert "Issue 09" not in body and "SECTION B: SPORTING REGULATIONS" not in body
    assert len(body) > 200


def test_wikipedia_sections_skip_tables_and_references():
    """Article text splits by heading; classification tables and references are dropped.

    Why: flattened tables are noise, and stats must come from query_stats (SPEC M3).
    """
    page = json.loads((FIX / "wikipedia_2024_italian_gp.json").read_text())["query"]["pages"][0]
    names = [s for s, _ in wikipedia_sections(page["extract"])]
    assert names[0] == "Summary" and "Background" in names
    assert not any("classification" in n.lower() or n == "References" for n in names)


def test_wikipedia_document_keeps_url_and_license_for_attribution():
    """Wikipedia documents carry title, canonical URL and the CC BY-SA licence.

    Why: CC BY-SA requires attribution; the chat UI shows these with every citation.
    """

    class FixtureFetcher:
        def get(self, url, params=None, refresh=False):
            return (FIX / "wikipedia_2024_italian_gp.json").read_bytes()

    doc = wikipedia_document(
        FixtureFetcher(), "2024 Italian Grand Prix", season=2024, event_id=202416
    )
    assert doc.url == "https://en.wikipedia.org/wiki/2024_Italian_Grand_Prix"
    assert (
        doc.license.startswith("CC BY-SA 4.0")
        and doc.source_key == "wikipedia:2024_Italian_Grand_Prix"
    )


def test_chunks_stay_within_sections_and_overlap():
    """Chunks never span sections, stay near the size limit and overlap their neighbour.

    Why: a citation names one section; overlap keeps a fact cut at a boundary findable.
    """
    long = "\n\n".join(f"Paragraph {i}. " + "word " * 60 for i in range(12))
    chunks = chunk_sections([("A", long), ("B", "short text")])
    a = [c for c in chunks if c.section == "A"]
    assert len(a) > 3 and chunks[-1].section == "B" and chunks[-1].content == "short text"
    assert all(len(c.content) <= MAX_CHARS + OVERLAP for c in chunks)
    assert a[0].content[-40:].split()[-1] in a[1].content[: OVERLAP + 40]


class FakeConn:
    """Returns canned rows per SQL statement (summaries issue four queries)."""

    def __init__(self, rows):
        self.rows = rows

    def execute(self, stmt, params=None):
        return SimpleNamespace(all=lambda: self.rows[stmt])


def _r(**kw):
    return SimpleNamespace(**kw)


def test_race_summary_template_reads_like_a_race_report():
    """The generated summary states winner, gap, pole, fastest lap, SCs, strategy, DNFs.

    Why: these summaries are the cited source for "what happened in race X" questions,
    so every fact in them must come straight from our data.
    """
    ev = _r(id=202416, season=2024, round=16, name="Italian Grand Prix",
            race_start_utc=None, circuit="Monza", locality="Monza")  # fmt: skip
    results = [
        _r(session="R", position=1, grid=4, status="Finished", time_ms=4480727, laps=53,
           id="leclerc", full_name="Charles Leclerc", team="Ferrari"),
        _r(session="R", position=2, grid=2, status="Finished", time_ms=4483391, laps=53,
           id="piastri", full_name="Oscar Piastri", team="McLaren"),
        _r(session="R", position=3, grid=1, status="Finished", time_ms=4486880, laps=53,
           id="norris", full_name="Lando Norris", team="McLaren"),
        _r(session="R", position=None, grid=12, status="Retired", time_ms=None, laps=7,
           id="tsunoda", full_name="Yuki Tsunoda", team="RB"),
        _r(session="Q", position=1, grid=None, status=None, time_ms=None, laps=None,
           id="norris", full_name="Lando Norris", team="McLaren"),
    ]  # fmt: skip
    laps = [_r(driver_id="norris", lap=53, lap_time_ms=81432, track_status="1")]
    laps += [
        _r(
            driver_id="leclerc",
            lap=n,
            lap_time_ms=83000,
            track_status="4" if n in (20, 21) else "1",
        )
        for n in range(1, 30)
    ]
    stints = [
        _r(compound="MEDIUM", start_lap=1, end_lap=15),
        _r(compound="HARD", start_lap=16, end_lap=53),
    ]
    conn = FakeConn(
        {summaries.RESULTS_SQL: results, summaries.LAPS_SQL: laps, summaries.STINTS_SQL: stints}
    )
    text_ = summaries.race_summary(conn, ev).sections[0][1]
    assert (
        "Charles Leclerc (Ferrari) won from 4th on the grid, 2.664 seconds ahead of Oscar Piastri"
        in text_
    )
    assert "Lando Norris started from pole position." in text_
    assert "fastest lap was 1:21.432 by Lando Norris on lap 53" in text_
    assert "1 safety car period (from lap 20)" in text_
    assert "1 pit stop: Medium for 15 laps, then Hard for 38 laps." in text_
    assert "Did not finish: Yuki Tsunoda." in text_


class FakeSession:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.bodies = []

    def post(self, url, json=None, headers=None, timeout=None):
        self.bodies.append(json)
        status, payload = self.responses.pop(0)
        return SimpleNamespace(
            status_code=status, headers={"retry-after": "0"},
            json=lambda: payload, text=str(payload),
        )  # fmt: skip


def _vectors(n, value=1.0):
    return {"embeddings": [{"values": [value] + [0.0] * (DIM - 1)} for _ in range(n)]}


def test_embedder_batches_retries_and_normalizes(monkeypatch):
    """Batches of 100, a 429 is retried, vectors come back unit-length.

    Why: the free embedding quota is per-minute; one rate limit must not drop the build.
    """
    monkeypatch.setattr("tracksync_etl.rag.embed.time.sleep", lambda s: None)
    session = FakeSession((429, {}), (200, _vectors(100, 3.0)), (200, _vectors(20, 3.0)))
    vecs = Embedder("key", session=session).embed(["t"] * 120, ["title"] * 120)
    assert len(vecs) == 120 and vecs[0][0] == pytest.approx(1.0)
    assert [len(b["requests"]) for b in session.bodies] == [100, 100, 20]
    assert session.bodies[0]["requests"][0]["taskType"] == "RETRIEVAL_DOCUMENT"
    assert Embedder("").embed(["t"], ["x"]) is None  # no key: full-text only


def test_embedder_stops_for_the_day_on_daily_quota(monkeypatch):
    """A per-day quota 429 is not retried, and later calls make no requests at all.

    Why: the free tier allows 1000 embedded texts a day; on 2026-11-15 the first full build
    hit it and then spent ~3 minutes per remaining document retrying a quota that resets
    the next day.
    """
    monkeypatch.setattr("tracksync_etl.rag.embed.time.sleep", lambda s: None)
    quota_id = "EmbedContentRequestsPerDayPerUserPerProjectPerModel-FreeTier"
    daily = {"error": {"details": [{"violations": [{"quotaId": quota_id}]}]}}
    session = FakeSession((429, daily))
    emb = Embedder("key", session=session)
    assert emb.embed(["t"], ["x"]) is None and emb.exhausted
    assert emb.embed(["t"], ["x"]) is None
    assert len(session.bodies) == 1


@pytest.mark.db
def test_store_documents_defers_unembedded_documents_when_quota_is_gone(rag_engine):
    """With the daily quota gone, an unembedded document is left alone, not rewritten.

    Why: rewriting it text-only gains nothing and churns the table; the next run embeds it.
    """
    doc = _doc("Pit lane speed limit text. " * 10)
    doc = Document(doc.source, "fia:defer-test", doc.title, doc.url, doc.sections, season=2026)
    store_documents(rag_engine, [doc], CountingEmbedder(enabled=False))
    gone = CountingEmbedder()
    gone.exhausted = True
    try:
        assert store_documents(rag_engine, [doc], gone)["rag_deferred"] == 1
        assert gone.calls == 0
    finally:  # other tests in this module count documents
        with rag_engine.begin() as conn:
            conn.execute(text("delete from rag_documents where source_key = 'fia:defer-test'"))


@pytest.fixture(scope="module")
def rag_engine(fresh_database):
    engine = make_engine(fresh_database("tracksync_test_rag"))
    yield engine
    engine.dispose()


def _doc(text_="Safety car rules apply. " * 20):
    return Document("fia", "fia:sporting:2026", "2026 F1 Sporting Regulations", "https://fia.test/r.pdf",
                    [("Article B5.13 Safety Car (SC)", text_)], season=2026)  # fmt: skip


class CountingEmbedder:
    def __init__(self, enabled=True):
        self.exhausted = False
        self.calls = 0
        self.enabled = enabled
        self.requests_made = 0

    def embed(self, texts, titles):
        if not self.enabled:
            return None
        self.calls += 1
        return [[1.0] + [0.0] * (DIM - 1) for _ in texts]


@pytest.mark.db
def test_store_documents_is_idempotent_and_reembeds_when_a_key_arrives(rag_engine):
    """Unchanged documents are skipped; changed ones are replaced; documents stored without
    embeddings are embedded on the first run that has a key.

    Why: the weekly ETL runs over every race; re-embedding unchanged text would burn the
    free quota, and a first run without a key must not leave search vectors missing forever.
    """
    no_key = CountingEmbedder(enabled=False)
    assert store_documents(rag_engine, [_doc()], no_key)["rag_documents"] == 1
    assert store_documents(rag_engine, [_doc()], no_key)["rag_unchanged"] == 1
    keyed = CountingEmbedder()
    assert store_documents(rag_engine, [_doc()], keyed)["rag_embedded"] > 0  # pending → embedded
    assert store_documents(rag_engine, [_doc()], keyed)["rag_unchanged"] == 1
    assert keyed.calls == 1
    store_documents(rag_engine, [_doc("New wording of the safety car article. " * 5)], keyed)
    with rag_engine.connect() as conn:
        docs = conn.execute(text("select count(*) from rag_documents")).scalar_one()
        chunks = conn.execute(
            text("select count(*), bool_and(embedding is not null) from rag_chunks")
        ).one()
        hit = conn.execute(
            text(
                "select section from rag_chunks "
                "where tsv @@ plainto_tsquery('english', 'safety car wording')"
            )
        ).scalar_one()
    assert docs == 1 and chunks[1] is True and hit.startswith("Article B5.13")


def test_fetcher_paces_requests_retries_throttling_and_caches(tmp_path):
    """Uncached requests are spaced out, a 429 is retried after Retry-After, and a cached
    response never hits the network again.

    Why: the first real build fired ~25 requests/s at Wikipedia and 81 of 93 race articles
    failed with throttling; the knowledge base silently missed most race history.
    """
    from tracksync_etl.rag.sources import Fetcher

    class Session:
        def __init__(self):
            self.headers = {}
            self.calls = 0

        def get(self, url, params=None, timeout=None):
            self.calls += 1
            status = 429 if self.calls == 1 else 200
            return SimpleNamespace(
                status_code=status, headers={"retry-after": "2"}, content=b"ok",
                raise_for_status=lambda: None,
            )  # fmt: skip

    sleeps = []
    session = Session()
    f = Fetcher(
        tmp_path, session=session, min_interval_s=0.5, sleep=sleeps.append, clock=lambda: 0.0
    )
    assert f.get("https://w.test/api", {"titles": "A"}) == b"ok"
    assert 2.0 in sleeps and session.calls == 2  # retried after Retry-After
    assert f.get("https://w.test/api", {"titles": "A"}) == b"ok" and session.calls == 2  # cached
    f.get("https://w.test/api", {"titles": "B"})
    assert any(0 < s <= 0.5 for s in sleeps)  # paced before the next uncached request

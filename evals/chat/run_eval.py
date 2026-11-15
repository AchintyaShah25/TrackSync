"""Chat agent evaluation (SPEC M3, decision 0029).

Three measurements on evals/chat/golden.jsonl:

1. Retrieval hit@5 (rules + history): is a passage from the expected FIA article or
   Wikipedia/summary document among the top 5 results of `search_knowledge`? No LLM needed.
2. Stats-tool compliance (stats): did the agent call `query_stats` with the expected query?
   This is the SPEC acceptance "stats answers come from query_stats, not retrieval".
3. Answer correctness (all): does the answer contain every expected key fact (any of the
   listed alternatives, case-insensitive)? Simple and deterministic; no LLM judge.

Usage (from the repo root; reads DATABASE_URL, GROQ_API_KEY, GEMINI_API_KEY):
  uv run --package tracksync-api python evals/chat/run_eval.py --check      # golden sanity
  uv run --package tracksync-api python evals/chat/run_eval.py              # retrieval only
  uv run --package tracksync-api python evals/chat/run_eval.py --agent      # + full agent
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
import unicodedata
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from app.config import Settings
from app.llm import AllProvidersDown, build_chain, embed_query
from app.schemas.chat import ChatMessage, ChatRequest
from app.services.chat import agent, knowledge
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

HERE = Path(__file__).parent
GOLDEN = HERE / "golden.jsonl"
TARGETS = {"retrieval_hit_at_5": 0.7, "stats_tool_compliance": 0.95}


def load() -> list[dict]:
    return [json.loads(line) for line in GOLDEN.read_text().splitlines() if line.strip()]


def source_matches(hit, expect: dict) -> bool:
    if "section" in expect:
        return hit.source == expect["source"] and expect["section"] in (hit.section or "")
    return expect["title"].lower() in hit.title.lower()


def _norm(text_: str) -> str:
    """Lowercase, NFKC, single spaces: models write non-breaking spaces and hyphens
    ("Red\u00a0Bull"), which must not count as a wrong answer."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text_)).lower()


def facts_found(answer: str, facts: list[list[str]]) -> bool:
    low = _norm(answer)
    return all(any(_norm(alt) in low for alt in group) for group in facts)


async def check_golden(conn, golden: list[dict]) -> int:
    """Each expected source exists, and each history fact appears in that source's text."""
    problems = 0
    for g in golden:
        exp = g.get("expect_source")
        if not exp:
            continue
        if "section" in exp:
            sql = (
                "select string_agg(c.content, ' ') from rag_chunks c join rag_documents d "
                "on d.id = c.document_id where d.source = :s and c.section like :sec"
            )
            params = {"s": exp["source"], "sec": f"Article {exp['section']}%"}
        else:
            sql = (
                "select string_agg(c.content, ' ') from rag_chunks c join rag_documents d "
                "on d.id = c.document_id where lower(d.title) like :t"
            )
            params = {"t": f"%{exp['title'].lower()}%"}
        corpus = (await conn.execute(text(sql), params)).scalar()
        if not corpus:
            print(f"  {g['id']}: expected source not in the knowledge base: {exp}")
            problems += 1
        elif g["category"] == "history" and not facts_found(corpus, g["facts"]):
            print(f"  {g['id']}: facts {g['facts']} not found in {exp['title']!r}")
            problems += 1
    print(f"golden check: {len(golden)} questions, {problems} problem(s)")
    return problems


async def run(args) -> int:
    settings = Settings(
        database_url=os.environ.get(
            "DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
        ),
        groq_api_key=os.environ.get("GROQ_API_KEY", ""),
        gemini_api_key=os.environ.get("GEMINI_API_KEY", ""),
    )
    engine = create_async_engine(settings.async_database_url)
    golden = load()
    if args.only:
        golden = [g for g in golden if g["category"] == args.only]
    if args.limit:
        golden = golden[: args.limit]

    async with engine.connect() as conn:
        if args.check:
            problems = await check_golden(conn, golden)
            await engine.dispose()
            return 1 if problems else 0

        # 1. Retrieval
        retrieval = {}
        embedded = await conn.scalar(
            text("select count(*) from rag_chunks where embedding is not null")
        )
        for g in golden:
            if g["category"] == "stats":
                continue
            vec = await embed_query(g["question"], settings.gemini_api_key)
            src = g["expect_source"].get("source")
            # By default search as the agent does: rules questions filter to FIA documents
            # (the system prompt tells it to); --unfiltered measures the harder open search.
            hits = await knowledge.search(
                conn, g["question"], vec, k=5, source=None if args.unfiltered else src
            )
            retrieval[g["id"]] = any(source_matches(h, g["expect_source"]) for h in hits)

        # 2 + 3. Agent
        answers: dict[str, dict] = {}
        todo = golden
        if args.retry_errors:
            # Keep earlier answers (re-graded below); ask only what failed last time.
            answers = json.loads((HERE / "results.json").read_text()).get("answers", {})
            todo = [g for g in golden if "correct" not in answers.get(g["id"], {})]
            print(f"retrying {len(todo)} unanswered question(s)")
        chain = build_chain(settings)
        if args.agent and not chain.configured:
            print("--agent needs GROQ_API_KEY and/or GEMINI_API_KEY; skipping agent evals")
        if args.agent and chain.configured:

            async def embed(q: str):
                return await embed_query(q, settings.gemini_api_key)

            for i, g in enumerate(todo):
                req = ChatRequest(messages=[ChatMessage(role="user", content=g["question"])])
                for _attempt in range(args.attempts):
                    try:
                        res = await agent.answer(conn, chain, embed, req)
                        break
                    except AllProvidersDown as err:
                        wait = min(err.retry_after + 2, 90)
                        print(f"  providers busy; waiting {wait:.0f}s")
                        await asyncio.sleep(wait)
                else:
                    answers[g["id"]] = {"error": "providers unavailable"}
                    continue
                answers[g["id"]] = {
                    "answer": res.answer,
                    "tools": res.tools_used,
                    "provider": res.provider,
                    "correct": facts_found(res.answer, g["facts"]),
                    "used_stats": "query_stats" in res.tools_used,
                    "cited": [s.title for s in res.sources],
                }
                print(f"  [{i + 1}/{len(todo)}] {g['id']}: correct={answers[g['id']]['correct']}")
                await asyncio.sleep(args.pause)
    await engine.dispose()
    facts = {g["id"]: g["facts"] for g in golden}
    for qid, a in answers.items():
        if "answer" in a and qid in facts:
            a["correct"] = facts_found(a["answer"], facts[qid])
    return report(golden, retrieval, answers, embedded or 0, args)


def rate(values: list[bool]) -> float | None:
    return round(sum(values) / len(values), 3) if values else None


def report(golden, retrieval, answers, embedded: int, args) -> int:
    by_cat: dict[str, list[bool]] = defaultdict(list)
    for g in golden:
        a = answers.get(g["id"])
        if a and "correct" in a:
            by_cat[g["category"]].append(a["correct"])
    stats_ids = [g["id"] for g in golden if g["category"] == "stats"]
    compliance = rate(
        [answers[i]["used_stats"] for i in stats_ids if "used_stats" in answers.get(i, {})]
    )
    results = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "questions": len(golden),
        "embedded_chunks": embedded,
        "retrieval_mode": "hybrid (vector + full-text)" if embedded else "full-text only",
        "retrieval_hit_at_5": rate(list(retrieval.values())),
        "retrieval_by_category": {
            cat: rate(
                [
                    retrieval[g["id"]]
                    for g in golden
                    if g["category"] == cat and g["id"] in retrieval
                ]
            )
            for cat in ("rules", "history")
        },
        "answered": sum(1 for a in answers.values() if "correct" in a),
        "unanswered": sorted(i for i, a in answers.items() if "correct" not in a),
        "answer_correctness": rate([v for vals in by_cat.values() for v in vals]),
        "answer_correctness_by_category": {c: rate(v) for c, v in sorted(by_cat.items())},
        "stats_tool_compliance": compliance,
        "retrieval_misses": sorted(i for i, ok in retrieval.items() if not ok),
        "wrong_answers": sorted(i for i, a in answers.items() if a.get("correct") is False),
        "answers": answers,
    }
    if not args.dry:
        (HERE / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
        write_markdown(results)
    print(json.dumps({k: v for k, v in results.items() if k != "answers"}, indent=2))
    failed = [k for k, target in TARGETS.items() if results[k] is not None and results[k] < target]
    if failed:
        print(f"below target: {failed} (targets {TARGETS})")
    return 1 if failed else 0


def write_markdown(r: dict) -> None:
    pct = lambda v: "n/a" if v is None else f"{v:.0%}"  # noqa: E731
    lines = [
        "# Chat agent evaluation",
        "",
        f"Generated {r['generated_at']} by `make eval` ([run_eval.py](run_eval.py)) on "
        f"[golden.jsonl](golden.jsonl): {r['questions']} questions (rules, history, stats). "
        f"Retrieval: {r['retrieval_mode']} ({r['embedded_chunks']} embedded chunks), searched as "
        "the agent does (rules questions filtered to FIA documents).",
        "",
        "| Metric | Score | Target |",
        "|---|---|---|",
        f"| Retrieval hit@5 (rules + history) | {pct(r['retrieval_hit_at_5'])} | 70% |",
        f"| … rules (FIA) | {pct(r['retrieval_by_category']['rules'])} | |",
        f"| … history (Wikipedia, summaries) | {pct(r['retrieval_by_category']['history'])} | |",
        f"| Stats answers that used `query_stats` | {pct(r['stats_tool_compliance'])} | 95% |",
        f"| Answer correctness (key facts), {r['answered']} answered | "
        f"{pct(r['answer_correctness'])} | |",
    ]
    for cat, v in r["answer_correctness_by_category"].items():
        lines.append(f"| … {cat} | {pct(v)} | |")
    lines += [
        "",
        f"Retrieval misses: {', '.join(r['retrieval_misses']) or 'none'}.  ",
        f"Wrong answers: {', '.join(r['wrong_answers']) or 'none'}.  ",
        f"Unanswered (providers busy): {', '.join(r['unanswered']) or 'none'}.",
        "",
    ]
    (HERE / "results.md").write_text("\n".join(lines))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--check", action="store_true", help="validate the golden set against sources")
    p.add_argument("--agent", action="store_true", help="also run the full agent (needs LLM keys)")
    p.add_argument("--only", choices=["rules", "history", "stats"])
    p.add_argument("--limit", type=int)
    p.add_argument("--pause", type=float, default=4.0, help="seconds between agent questions")
    p.add_argument(
        "--unfiltered", action="store_true", help="search all sources even for rules questions"
    )
    p.add_argument("--attempts", type=int, default=6, help="tries per question when busy")
    p.add_argument(
        "--retry-errors", action="store_true", help="re-ask only questions unanswered last run"
    )
    p.add_argument("--dry", action="store_true", help="print only; do not write results files")
    t0 = time.monotonic()
    code = asyncio.run(run(p.parse_args()))
    print(f"done in {time.monotonic() - t0:.0f}s")
    return code


if __name__ == "__main__":
    sys.exit(main())

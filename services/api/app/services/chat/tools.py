"""Tool definitions the model sees, and the dispatcher that runs them (decision 0029).

Tools are read-only. Results go back to the model as compact JSON. Retrieved passages are
numbered for citation ([1], [2], ...) across the whole turn, and chartable query results
are registered as datasets that `make_chart` can reference by name. The model never passes
numbers to plot, so charts cannot show invented data.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncConnection

from ...schemas.chat import ChartSeries, ChartSpec, SourceOut
from ...schemas.strategy import SimulateRequest, StintIn, StrategyIn
from .. import strategy as strategy_service
from . import knowledge
from .stats import QUERIES, Dataset, StatsContext, StatsError, run_query

log = logging.getLogger(__name__)

MAX_TOOL_OUTPUT = 6000
MAX_CHARTS = 2
MAX_CHART_POINTS = 300
LETTER = {"S": "SOFT", "M": "MEDIUM", "H": "HARD"}

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": (
                "Search FIA F1 regulations (rules, penalties, procedures, points), Wikipedia "
                "articles about seasons and races (history, context, incidents) and race "
                "summaries. Returns numbered passages to cite as [n]."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to look for, in words."},
                    "source": {
                        "type": "string",
                        "enum": ["fia", "wikipedia", "summary"],
                        "description": "Optional: fia for rules, wikipedia for history.",
                    },
                    "season": {"type": "integer", "description": "Optional season filter."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_stats",
            "description": (
                "Get results, standings, lap times, strategies and other numbers from the "
                "TrackSync database (2023 onward). Always use this for any statistic. Queries: "
                + "; ".join(f"{name}: {desc}" for name, (_, desc) in QUERIES.items())
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "enum": sorted(QUERIES)},
                    "params": {
                        "type": "object",
                        "description": 'Query parameters, e.g. {"season": 2024, "race": "Monza"}.',
                    },
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "simulate_strategy",
            "description": (
                "Monte Carlo what-if for a driver in a past dry race: compare up to 3 pit "
                "strategies with the one they really used. Strategy format: compound letter + "
                "laps per stint, e.g. 'M20-H33' (S, M or H; two compounds; laps add up to the "
                "race distance)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "season": {"type": "integer"},
                    "race": {"type": "string"},
                    "driver": {"type": "string"},
                    "strategies": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
                    "safety_cars": {"type": "string", "enum": ["random", "actual"]},
                },
                "required": ["race", "driver", "strategies"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "make_chart",
            "description": (
                "Show a chart in the answer. Only use dataset names listed under 'chartable' "
                "in earlier query_stats results; up to 4 datasets of the same kind."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "datasets": {"type": "array", "items": {"type": "string"}, "maxItems": 4},
                },
                "required": ["title", "datasets"],
            },
        },
    },
]


@dataclass
class TurnState:
    """Everything one chat turn accumulates across tool calls."""

    conn: AsyncConnection
    embed: Any  # async (text) -> list[float] | None
    stats: StatsContext = field(init=False)
    sources: list[SourceOut] = field(default_factory=list)
    charts: list[ChartSpec] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    _seen_chunks: dict[int, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.stats = StatsContext(self.conn)


def _dump(value: Any) -> str:
    out = json.dumps(value, ensure_ascii=False, default=str)
    return out if len(out) <= MAX_TOOL_OUTPUT else out[:MAX_TOOL_OUTPUT] + "…(truncated)"


async def run_tool(state: TurnState, name: str, raw_args: str | dict | None) -> str:
    try:
        args = raw_args if isinstance(raw_args, dict) else json.loads(raw_args or "{}")
        if not isinstance(args, dict):
            raise ValueError("arguments must be an object")
    except (ValueError, TypeError):
        return _dump({"error": "arguments were not valid JSON"})
    state.tools_used.append(name)
    try:
        if name == "search_knowledge":
            return await _search(state, args)
        if name == "query_stats":
            params = args.get("params") if isinstance(args.get("params"), dict) else {}
            return _dump(await run_query(state.stats, str(args.get("name", "")), params))
        if name == "simulate_strategy":
            return await _simulate(state, args)
        if name == "make_chart":
            return _chart(state, args)
        return _dump({"error": f"unknown tool {name!r}"})
    except StatsError as err:
        return _dump({"error": str(err)})
    except strategy_service.StrategyError as err:
        return _dump({"error": err.detail})


async def _search(state: TurnState, args: dict) -> str:
    query = str(args.get("query", ""))[:500]
    season = args.get("season")
    hits = await knowledge.search(
        state.conn,
        query,
        await state.embed(query),
        k=5,
        source=args.get("source"),
        season=int(season) if str(season or "").isdigit() else None,
    )
    if not hits:
        return _dump({"passages": [], "note": "nothing found; say you could not find it"})
    passages = []
    for h in hits:
        n = state._seen_chunks.get(h.chunk_id)
        if n is None:
            n = len(state.sources) + 1
            state._seen_chunks[h.chunk_id] = n
            state.sources.append(
                SourceOut(n=n, title=h.title, section=h.section, url=h.url, license=h.license,
                          source=h.source, excerpt=h.content[:400])
            )  # fmt: skip
        passages.append({"n": n, "from": f"{h.title} — {h.section or ''}", "text": h.content})
    return _dump({"passages": passages, "cite_as": "[n]"})


def _parse_strategy(code: str) -> list[StintIn]:
    stints = []
    for part in str(code).upper().replace(" ", "").split("-"):
        if len(part) < 2 or part[0] not in LETTER or not part[1:].isdigit():
            raise StatsError(f"strategy {code!r} must look like 'M20-H33'")
        stints.append(StintIn(compound=LETTER[part[0]], laps=int(part[1:])))  # type: ignore[arg-type]
    return stints


async def _simulate(state: TurnState, args: dict) -> str:
    from .stats import _driver, _event  # name resolution shared with query_stats

    season = args.get("season")
    ev = await _event(
        state.stats, int(season) if str(season or "").isdigit() else None, args.get("race")
    )
    driver = await _driver(state.stats, args.get("driver"))
    codes = [c for c in (args.get("strategies") or []) if isinstance(c, str)][:3]
    if not codes:
        raise StatsError("give 1-3 strategies like 'M20-H33'")
    req = SimulateRequest(
        event_id=ev.id,
        driver_id=driver.id,
        strategies=[StrategyIn(label=c.upper(), stints=_parse_strategy(c)) for c in codes],
        safety_cars="actual" if args.get("safety_cars") == "actual" else "random",
        seed=7,
        runs=500,
    )
    res = await strategy_service.simulate_strategies(state.conn, req)
    rows = []
    for s in res.strategies:
        rows.append(
            {
                "strategy": s.label,
                "median_finish_vs_real_s": s.finish_delta_s.p50,
                "range_90pct_s": [s.finish_delta_s.p5, s.finish_delta_s.p95],
                "p_finish_ahead_of_real_result": s.p_gain,
                "p_finish_behind": s.p_lose,
            }
        )
        state.stats.register(
            f"sim:{ev.id}:{driver.code}:{s.label}",
            Dataset(f"{s.label} gap to real strategy (median)", "line", "Lap", "Seconds ahead",
                    [(i + 1, -v) for i, v in enumerate(s.gap.p50)]),
        )  # fmt: skip
    real = "-".join(f"{st.compound[0]}{st.laps}" for st in res.actual.stints)
    return _dump(
        {
            "race": f"{ev.season} {ev.name}",
            "driver": driver.full_name,
            "real_strategy": real,
            "real_result": res.actual.position,
            "negative_means_faster": True,
            "results": rows,
            "page": f"/races/{ev.season}/{ev.round}/forecast",
            "chartable": [f"sim:{ev.id}:{driver.code}:{s.label}" for s in res.strategies],
        }
    )


def _chart(state: TurnState, args: dict) -> str:
    if len(state.charts) >= MAX_CHARTS:
        return _dump({"error": f"at most {MAX_CHARTS} charts per answer"})
    refs = [r for r in (args.get("datasets") or []) if isinstance(r, str)][:4]
    missing = [r for r in refs if r not in state.stats.datasets]
    if not refs or missing:
        return _dump({
            "error": "unknown dataset name(s); use names from 'chartable' in earlier results",
            "unknown": missing,
            "available": sorted(state.stats.datasets),
        })  # fmt: skip
    sets = [state.stats.datasets[r] for r in refs]
    if len({d.kind for d in sets}) > 1:
        return _dump({"error": "datasets must all be lines or all be bars"})
    first = sets[0]
    spec = ChartSpec(
        type=first.kind,  # type: ignore[arg-type]
        title=str(args.get("title") or first.name)[:120],
        x_label=first.x_label,
        y_label=first.y_label,
        series=[
            ChartSeries(
                name=d.name,
                points=[[x, round(float(y), 3)] for x, y in d.points][:MAX_CHART_POINTS],
            )
            for d in sets
        ],
    )
    state.charts.append(spec)
    return _dump(
        {
            "ok": True,
            "note": "the chart is shown below your answer; do not repeat its numbers in full",
        }
    )


__all__ = ["TOOLS", "TurnState", "run_tool"]

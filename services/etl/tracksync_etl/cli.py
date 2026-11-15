"""tracksync-etl command line.

tracksync-etl --season 2024                 # whole season (completed events)
tracksync-etl --season 2024 --event 16      # one event
tracksync-etl --since-days 8                # scheduled mode: recent + missing events
tracksync-etl --season 2024 --event 16 --dry-run
tracksync-etl --fit-models                  # refit the race model only (no ingest)
tracksync-etl --rag                         # rebuild the chat knowledge base only
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from collections import Counter
from datetime import UTC, datetime, timedelta

from . import fit_models
from .config import Settings, configure_fastf1
from .load.db import Store, make_engine
from .pipeline import Pipeline
from .rag.build import refresh_knowledge
from .rag.embed import Embedder
from .sources.openf1 import OpenF1Client
from .transform.reference import is_completed

log = logging.getLogger("tracksync_etl")
FIRST_SEASON = 2023  # OpenF1 historical coverage starts here (SPEC: 2023+)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="tracksync-etl", description=__doc__.split("\n\n")[0])
    p.add_argument("--season", type=int, help="season year (2023 or later)")
    p.add_argument("--event", type=int, help="round number within --season")
    p.add_argument(
        "--since-days",
        type=int,
        help="scheduled mode: ingest events that finished in the last N days, plus any "
        "completed events of the current season still missing data",
    )
    p.add_argument("--refresh-circuits", action="store_true", help="rebuild circuit outlines")
    p.add_argument("--dry-run", action="store_true", help="fetch and transform, write nothing")
    p.add_argument(
        "--fit-models",
        action="store_true",
        help="refit the race model for every circuit; alone, it skips ingestion "
        "(a run that loads events always refits afterwards)",
    )
    p.add_argument(
        "--rag",
        action="store_true",
        help="rebuild the chat knowledge base (FIA regulations, Wikipedia, race summaries); "
        "alone, it skips ingestion (a run that loads events refreshes those races)",
    )
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)
    if args.since_days is None and args.season is None and not (args.fit_models or args.rag):
        p.error("give --season (optionally with --event), --since-days, --fit-models or --rag")
    if (args.fit_models or args.rag) and args.dry_run:
        p.error("--fit-models and --rag write to the database; they cannot be dry runs")
    if args.event is not None and args.season is None:
        p.error("--event needs --season")
    if args.season is not None and args.season < FIRST_SEASON:
        p.error(f"seasons before {FIRST_SEASON} are out of scope (v2 backlog)")
    return args


def select_events(events, args, store, now) -> list[dict]:
    """Completed events to ingest. --event wins; --since-days also picks up missing ones."""
    done = [e for e in events if is_completed(e, now)]
    if args.event is not None:
        return [e for e in done if e["round"] == args.event]
    if args.since_days is None:
        return done
    cutoff = now - timedelta(days=args.since_days)
    recent = [e for e in done if e["race_start_utc"] >= cutoff]
    if store is None:  # dry run: no DB to check for missing events
        return recent
    with store.engine.connect() as conn:
        return [e for e in done if e in recent or not store.has_session_data(conn, e["id"])]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = Settings.from_env()
    configure_fastf1(settings.fastf1_cache)
    now = datetime.now(UTC)

    store = None if args.dry_run else Store(make_engine(settings.database_url))
    openf1 = OpenF1Client(settings.openf1_cache, per_minute=settings.openf1_max_per_minute)
    pipeline = Pipeline(store, openf1, now=now, refresh_circuits=args.refresh_circuits)

    fit_only = (args.fit_models or args.rag) and args.season is None and args.since_days is None
    seasons = [] if fit_only else [args.season] if args.season else [now.year]
    run_id = store.start_run(vars(args)) if store else None
    totals: Counter = Counter()
    skipped: dict[int, list[str]] = {}
    failures: dict[int, str] = {}
    status, error = "ok", None
    started = time.monotonic()
    loaded_any = False
    loaded_ids: list[int] = []
    fit_error: str | None = None
    rag_error: str | None = None
    try:
        for season in seasons:
            events = pipeline.ingest_schedule(season)
            chosen = select_events(events, args, store, now)
            if args.event is not None and not chosen:
                log.error("round %s of %s not found or not finished yet", args.event, season)
                status = "failed"
            for event in chosen:
                try:
                    report = pipeline.ingest_event(event)
                except Exception as exc:
                    # One bad event must not abort a season backfill. Its transaction was
                    # rolled back; record it, exit non-zero at the end, and move on.
                    log.exception("event %d failed", event["id"])
                    failures[event["id"]] = f"{type(exc).__name__}: {str(exc)[:300]}"
                    continue
                totals.update(report.counts)
                if report.counts.get("laps"):
                    loaded_any = True
                    loaded_ids.append(event["id"])
                if report.skipped:
                    skipped[event["id"]] = report.skipped
                    status = "partial" if status == "ok" else status
                log.info("event %d: %s %s", event["id"], dict(report.counts), report.skipped or "")
            totals["standings"] += pipeline.ingest_standings(season)
        if store and (args.fit_models or loaded_any):
            try:
                totals["model_params"] = fit_models.refit_all(store)
            except Exception as exc:
                # Loaded data is already committed; fail the run so the stale model is noticed.
                log.exception("model fit failed")
                fit_error = f"{type(exc).__name__}: {str(exc)[:300]}"
        if store and (args.rag or loaded_ids):
            try:
                totals.update(
                    refresh_knowledge(
                        store.engine,
                        settings.rag_cache,
                        Embedder(settings.gemini_api_key),
                        event_ids=loaded_ids,
                        full=args.rag,
                        seasons=list(range(FIRST_SEASON, now.year + 1)),
                        current_season=now.year,
                    )
                )
            except Exception as exc:
                log.exception("knowledge base refresh failed")
                rag_error = f"{type(exc).__name__}: {str(exc)[:300]}"
        problems = []
        if failures:
            problems.append(f"{len(failures)} event(s) failed: {sorted(failures)}")
        if fit_error:
            problems.append(f"model fit failed: {fit_error}")
        if rag_error:
            problems.append(f"knowledge base refresh failed: {rag_error}")
        if problems:
            status = "failed"
            error = "; ".join(problems)
    except Exception as exc:  # recorded in etl_runs, then re-raised for a red CI job
        status, error = "failed", f"{type(exc).__name__}: {exc}"
        raise
    finally:
        summary = {
            **dict(totals),
            "skipped": {str(k): v for k, v in skipped.items()},
            "failed_events": {str(k): v for k, v in failures.items()},
            **({"model_fit_error": fit_error} if fit_error else {}),
            **({"rag_error": rag_error} if rag_error else {}),
            "openf1_requests": openf1.requests_made,
            "seconds": round(time.monotonic() - started),
        }
        if store and run_id is not None:
            store.finish_run(run_id, status, summary, error)
        log.info("run %s: %s", status, summary)
    return 0 if status in ("ok", "partial") else 1


if __name__ == "__main__":
    sys.exit(main())

"""Jolpica-F1 (Ergast-compatible) access through FastF1's interface.

Gives the schedule, official results, standings, and the stable Jolpica IDs we use as
primary keys (docs/decisions/0005). Returns plain pandas DataFrames.
"""

from __future__ import annotations

import functools
import logging
import time

import pandas as pd
import requests

log = logging.getLogger(__name__)


RATE_LIMIT_DELAY = 60.0


def _is_rate_limited(exc: Exception) -> bool:
    """FastF1 reports Jolpica's HTTP 429 as ErgastInvalidRequestError('... Too Many Requests')."""
    from fastf1.exceptions import ErgastInvalidRequestError

    return isinstance(exc, ErgastInvalidRequestError) and "Too Many Requests" in str(exc)


def retry_transient(fn=None, *, attempts: int = 4, base_delay: float = 5.0, sleep=time.sleep):
    """Retry dropped connections, timeouts and rate limits (FastF1's Ergast client doesn't).

    During the 2026-11-14 backfill, Zandvoort 2024 failed first on a dropped connection, then
    on a Jolpica 429 when re-run quickly after the 2023 re-run.
    """

    def wrap(f):
        @functools.wraps(f)
        def inner(*args, **kwargs):
            for attempt in range(1, attempts + 1):
                try:
                    return f(*args, **kwargs)
                except Exception as exc:
                    network = isinstance(exc, (requests.ConnectionError, requests.Timeout))
                    limited = _is_rate_limited(exc)
                    if not (network or limited) or attempt == attempts:
                        raise
                    delay = (
                        RATE_LIMIT_DELAY * attempt if limited else base_delay * 2 ** (attempt - 1)
                    )
                    log.warning(
                        "Jolpica %s failed (%s), retry %d in %.0fs", f.__name__, exc, attempt, delay
                    )
                    sleep(delay)

        return inner

    return wrap(fn) if fn else wrap


def _ergast():
    from fastf1.ergast import Ergast

    return Ergast(result_type="pandas", auto_cast=True)


def _first(resp) -> pd.DataFrame:
    return resp.content[0] if getattr(resp, "content", None) else pd.DataFrame()


@retry_transient
def schedule(season: int) -> pd.DataFrame:
    return _ergast().get_race_schedule(season)


@retry_transient
def race_results(season: int, rnd: int) -> pd.DataFrame:
    return _first(_ergast().get_race_results(season, rnd))


@retry_transient
def sprint_results(season: int, rnd: int) -> pd.DataFrame:
    return _first(_ergast().get_sprint_results(season, rnd))


@retry_transient
def qualifying_results(season: int, rnd: int) -> pd.DataFrame:
    return _first(_ergast().get_qualifying_results(season, rnd))


@retry_transient
def driver_standings(season: int) -> tuple[pd.DataFrame, int | None]:
    resp = _ergast().get_driver_standings(season)
    return _first(resp), _last_round(resp)


@retry_transient
def constructor_standings(season: int) -> tuple[pd.DataFrame, int | None]:
    resp = _ergast().get_constructor_standings(season)
    return _first(resp), _last_round(resp)


def _last_round(resp) -> int | None:
    desc = getattr(resp, "description", None)
    if desc is None or desc.empty:
        return None
    return int(desc["round"].iloc[-1])

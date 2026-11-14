"""Jolpica-F1 (Ergast-compatible) access through FastF1's interface.

Gives the schedule, official results, standings, and the stable Jolpica IDs we use as
primary keys (docs/decisions/0005). Returns plain pandas DataFrames.
"""

from __future__ import annotations

import pandas as pd


def _ergast():
    from fastf1.ergast import Ergast

    return Ergast(result_type="pandas", auto_cast=True)


def _first(resp) -> pd.DataFrame:
    return resp.content[0] if getattr(resp, "content", None) else pd.DataFrame()


def schedule(season: int) -> pd.DataFrame:
    return _ergast().get_race_schedule(season)


def race_results(season: int, rnd: int) -> pd.DataFrame:
    return _first(_ergast().get_race_results(season, rnd))


def sprint_results(season: int, rnd: int) -> pd.DataFrame:
    return _first(_ergast().get_sprint_results(season, rnd))


def qualifying_results(season: int, rnd: int) -> pd.DataFrame:
    return _first(_ergast().get_qualifying_results(season, rnd))


def driver_standings(season: int) -> tuple[pd.DataFrame, int | None]:
    resp = _ergast().get_driver_standings(season)
    return _first(resp), _last_round(resp)


def constructor_standings(season: int) -> tuple[pd.DataFrame, int | None]:
    resp = _ergast().get_constructor_standings(season)
    return _first(resp), _last_round(resp)


def _last_round(resp) -> int | None:
    desc = getattr(resp, "description", None)
    if desc is None or desc.empty:
        return None
    return int(desc["round"].iloc[-1])

"""Small helpers shared by transforms."""

from __future__ import annotations

import math
import re
import unicodedata
from typing import Any

import pandas as pd


def event_id(season: int, rnd: int) -> int:
    """Deterministic event key: season * 100 + round (docs/decisions/0005)."""
    return season * 100 + rnd


def slugify(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")


def clean(value: Any) -> Any:
    """Convert pandas/numpy scalars to plain Python; NaN/NaT become None."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if value is pd.NaT:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        return value.item()
    return value


def to_int(value: Any) -> int | None:
    v = clean(value)
    if v is None or v == "":
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def timedelta_ms(value: Any) -> int | None:
    v = clean(value)
    if v is None:
        return None
    if isinstance(v, pd.Timedelta):
        return int(v.total_seconds() * 1000)
    if isinstance(v, (int, float)):
        return int(v)
    return None

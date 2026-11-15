"""Circuit rotation and corner markers from MultiViewer, via fastf1.mvapi (no login)."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class CircuitInfo:
    rotation_deg: float
    corners: pd.DataFrame  # columns X, Y, Number, Letter, Angle


def fetch(year: int, circuit_key: int) -> CircuitInfo | None:
    from fastf1.mvapi import get_circuit_info

    info = get_circuit_info(year=year, circuit_key=circuit_key)
    if info is None:
        return None
    return CircuitInfo(rotation_deg=float(info.rotation), corners=info.corners)

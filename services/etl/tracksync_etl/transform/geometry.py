"""Fastest-lap traces and circuit outlines (docs/decisions/0006, 0007).

Traces: OpenF1 car_data (~3.7 Hz) and location samples for one lap are merged on time,
distance is integrated from speed, and every channel is resampled onto a uniform
distance grid of TRACE_POINTS, scaled to a common reference length so two drivers'
traces share the same x-axis.

Outline: the reference lap's X/Y is rotated by the MultiViewer rotation, smoothed with
a periodic Savitzky-Golay filter, resampled by arc length, and normalized into a unit
box (aspect kept). Traces and corners are mapped into the same frame, so the
frontend can draw them together without further math.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np

TRACE_POINTS = 300
OUTLINE_POINTS = 400

Row = dict[str, Any]


def _epoch(ts: str) -> float:
    return datetime.fromisoformat(ts).timestamp()


@dataclass(frozen=True)
class LapSamples:
    """Raw samples of one lap, time in seconds from the lap start."""

    t: np.ndarray
    speed: np.ndarray  # km/h
    throttle: np.ndarray  # 0-100
    brake: np.ndarray  # 0/1
    gear: np.ndarray
    x: np.ndarray
    y: np.ndarray
    duration: float


def lap_samples(
    car_data: list[Row], location: list[Row], lap_start: str, lap_duration: float
) -> LapSamples | None:
    """Merge car_data and location for one lap. None if there is too little data."""
    t0 = _epoch(lap_start)
    car = sorted((r for r in car_data if r.get("date")), key=lambda r: r["date"])
    loc = sorted((r for r in location if r.get("date")), key=lambda r: r["date"])
    if len(car) < 20 or len(loc) < 20:
        return None
    ct = np.array([_epoch(r["date"]) - t0 for r in car])
    lt = np.array([_epoch(r["date"]) - t0 for r in loc])
    speed = np.array([r.get("speed") or 0 for r in car], dtype=float)
    throttle = np.clip(np.array([r.get("throttle") or 0 for r in car], dtype=float), 0, 100)
    brake = (np.array([r.get("brake") or 0 for r in car], dtype=float) > 0).astype(float)
    gear = np.array([r.get("n_gear") or 0 for r in car], dtype=float)
    lx = np.array([r["x"] for r in loc], dtype=float)
    ly = np.array([r["y"] for r in loc], dtype=float)
    # Location is interpolated onto car_data timestamps (both ~3.7 Hz, not aligned).
    x = np.interp(ct, lt, lx)
    y = np.interp(ct, lt, ly)
    keep = (ct >= -0.5) & (ct <= lap_duration + 0.5)
    if keep.sum() < 20:
        return None
    return LapSamples(
        ct[keep],
        speed[keep],
        throttle[keep],
        brake[keep],
        gear[keep],
        x[keep],
        y[keep],
        lap_duration,
    )


def integrated_distance(s: LapSamples) -> np.ndarray:
    """Cumulative distance in metres from the lap start (trapezoid on speed)."""
    v = s.speed / 3.6
    d = np.concatenate([[0.0], np.cumsum(np.diff(s.t) * (v[1:] + v[:-1]) / 2)])
    # Shift so distance is 0 at t=0 (samples may start slightly before the line).
    return d - np.interp(0.0, s.t, d)


def lap_length(s: LapSamples) -> float:
    d = integrated_distance(s)
    return float(np.interp(s.duration, s.t, d))


@dataclass(frozen=True)
class Frame:
    """Rotation + normalization shared by the outline, traces and corners of an event."""

    rotation_deg: float
    origin: tuple[float, float]
    scale: float

    def apply(self, x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        rx, ry = rotate(x, y, self.rotation_deg)
        return (rx - self.origin[0]) / self.scale, (ry - self.origin[1]) / self.scale


def rotate(x: np.ndarray, y: np.ndarray, rotation_deg: float) -> tuple[np.ndarray, np.ndarray]:
    """Same rotation FastF1's track-map example applies with CircuitInfo.rotation."""
    a = np.deg2rad(rotation_deg)
    return x * np.cos(a) - y * np.sin(a), x * np.sin(a) + y * np.cos(a)


def build_trace(s: LapSamples, ref_length: float, frame: Frame) -> dict[str, list]:
    """Columnar trace on a uniform grid of TRACE_POINTS over [0, ref_length]."""
    d = integrated_distance(s)
    own_length = float(np.interp(s.duration, s.t, d))
    d_scaled = d * (ref_length / own_length) if own_length > 0 else d
    grid = np.linspace(0, ref_length, TRACE_POINTS)
    order = np.argsort(d_scaled, kind="stable")
    ds = d_scaled[order]

    def cont(v: np.ndarray) -> np.ndarray:
        return np.interp(grid, ds, v[order])

    def nearest(v: np.ndarray) -> np.ndarray:
        idx = np.clip(np.searchsorted(ds, grid), 0, len(ds) - 1)
        prev = np.clip(idx - 1, 0, len(ds) - 1)
        pick = np.where(np.abs(ds[prev] - grid) < np.abs(ds[idx] - grid), prev, idx)
        return v[order][pick]

    nx, ny = frame.apply(cont(s.x), cont(s.y))
    return {
        "d": np.round(grid, 1).tolist(),
        "speed": np.round(cont(s.speed), 1).tolist(),
        "throttle": np.round(cont(s.throttle)).astype(int).tolist(),
        "brake": nearest(s.brake).astype(int).tolist(),
        "gear": nearest(s.gear).astype(int).tolist(),
        "x": np.round(nx, 4).tolist(),
        "y": np.round(ny, 4).tolist(),
    }


def _resample_closed(x: np.ndarray, y: np.ndarray, n: int) -> tuple[np.ndarray, np.ndarray]:
    xs, ys = np.append(x, x[0]), np.append(y, y[0])
    seg = np.hypot(np.diff(xs), np.diff(ys))
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    target = np.linspace(0, cum[-1], n, endpoint=False)
    return np.interp(target, cum, xs), np.interp(target, cum, ys)


def build_outline(
    s: LapSamples, rotation_deg: float, points: int = OUTLINE_POINTS
) -> tuple[dict[str, list], Frame]:
    """Outline in a unit box (longest side = 1) plus the frame used to produce it."""
    from scipy.signal import savgol_filter  # scipy ships with FastF1

    inside = (s.t >= 0) & (s.t <= s.duration)
    x, y = s.x[inside], s.y[inside]
    # Drop repeated samples (car_data is denser than location in places).
    moved = np.concatenate([[True], np.hypot(np.diff(x), np.diff(y)) > 1e-6])
    x, y = x[moved], y[moved]
    x, y = _resample_closed(x, y, points)
    window = min(15, (points // 2) * 2 - 1)
    x = savgol_filter(x, window, 3, mode="wrap")
    y = savgol_filter(y, window, 3, mode="wrap")
    rx, ry = rotate(x, y, rotation_deg)
    origin = (float(rx.min()), float(ry.min()))
    scale = float(max(rx.max() - rx.min(), ry.max() - ry.min())) or 1.0
    frame = Frame(rotation_deg, origin, scale)
    nx, ny = (rx - origin[0]) / scale, (ry - origin[1]) / scale
    return {"x": np.round(nx, 4).tolist(), "y": np.round(ny, 4).tolist()}, frame


def build_corners(corners: list[Row], frame: Frame) -> list[Row]:
    """MultiViewer corner markers mapped into the outline frame."""
    if not corners:
        return []
    x = np.array([c["X"] for c in corners], dtype=float)
    y = np.array([c["Y"] for c in corners], dtype=float)
    nx, ny = frame.apply(x, y)
    return [
        {
            "number": int(c["Number"]),
            "letter": str(c.get("Letter") or ""),
            "x": round(float(px), 4),
            "y": round(float(py), 4),
            "angle": round(float(c.get("Angle") or 0.0) + frame.rotation_deg, 1),
        }
        for c, px, py in zip(corners, nx, ny, strict=True)
    ]

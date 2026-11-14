from datetime import UTC, datetime, timedelta

import numpy as np
from pitwall_etl.transform.geometry import (
    TRACE_POINTS,
    Frame,
    build_corners,
    build_outline,
    build_trace,
    lap_length,
    lap_samples,
    rotate,
)

T0 = datetime(2024, 9, 1, 13, 40, tzinfo=UTC)


def circle_lap(radius=1000.0, speed_kmh=180.0, hz=3.7, phase=0.0):
    """Synthetic lap around a circle at constant speed, sampled like OpenF1."""
    circumference = 2 * np.pi * radius  # in metres; location units are arbitrary here
    duration = circumference / (speed_kmh / 3.6)
    t = np.arange(-0.5, duration + 0.5, 1 / hz) + phase
    ang = 2 * np.pi * t / duration
    car = [
        {
            "date": (T0 + timedelta(seconds=float(s))).isoformat(),
            "speed": speed_kmh,
            "throttle": 100,
            "brake": 0,
            "n_gear": 7,
        }
        for s in t
    ]
    loc = [
        {
            "date": (T0 + timedelta(seconds=float(s))).isoformat(),
            "x": radius * np.cos(a),
            "y": radius * np.sin(a),
        }
        for s, a in zip(t, ang, strict=True)
    ]
    return car, loc, duration, circumference


def test_lap_length_matches_integrated_speed():
    """Distance integrated from speed reproduces the true lap length within 0.5%.

    Why: the trace x-axis is distance; a drifting integral would misalign braking points.
    """
    car, loc, duration, circumference = circle_lap()
    s = lap_samples(car, loc, T0.isoformat(), duration)
    assert abs(lap_length(s) - circumference) / circumference < 0.005


def test_trace_is_columnar_uniform_and_shares_grid_across_drivers():
    """Traces have TRACE_POINTS samples per channel on one shared distance grid.

    Why: the telemetry comparison overlays two drivers point by point on the same x-axis,
    and the columnar layout keeps storage small (docs/decisions/0006).
    """
    car, loc, duration, circ = circle_lap()
    car2, loc2, duration2, _ = circle_lap(speed_kmh=175)
    frame = Frame(0.0, (-1000.0, -1000.0), 2000.0)
    a = build_trace(lap_samples(car, loc, T0.isoformat(), duration), circ, frame)
    b = build_trace(lap_samples(car2, loc2, T0.isoformat(), duration2), circ, frame)
    assert set(a) == {"d", "speed", "throttle", "brake", "gear", "x", "y"}
    assert all(len(v) == TRACE_POINTS for v in a.values())
    assert a["d"] == b["d"]
    assert a["d"][0] == 0 and abs(a["d"][-1] - circ) < 1
    assert min(a["x"]) >= 0 and max(a["x"]) <= 1


def test_outline_is_normalized_closed_and_rotated():
    """The outline fits a unit box with the longest side = 1 and has OUTLINE_POINTS points.

    Why: the track map renders it directly in an SVG viewBox; the frame must also map the
    corner markers onto the same coordinates.
    """
    car, loc, duration, _ = circle_lap()
    s = lap_samples(car, loc, T0.isoformat(), duration)
    outline, frame = build_outline(s, rotation_deg=90, points=400)
    x, y = np.array(outline["x"]), np.array(outline["y"])
    assert len(x) == 400
    assert abs(max(x.max() - x.min(), y.max() - y.min()) - 1) < 1e-3
    corner = build_corners(
        [{"X": 1000.0, "Y": 0.0, "Number": 1, "Letter": "", "Angle": 0.0}], frame
    )
    # A point on the circle maps onto the outline.
    d = np.hypot(x - corner[0]["x"], y - corner[0]["y"]).min()
    assert d < 0.01


def test_rotate_matches_fastf1_convention():
    """Rotating (1, 0) by 90 degrees gives (0, 1), like FastF1's track-map example.

    Why: circuits must appear in the orientation of the official track maps.
    """
    x, y = rotate(np.array([1.0]), np.array([0.0]), 90)
    assert np.allclose([x[0], y[0]], [0, 1])


def test_lap_samples_rejects_sparse_data():
    """A lap with too few samples yields no trace instead of a garbage one.

    Why: OpenF1 occasionally has gaps; a 5-point trace would mislead the chart.
    """
    car, loc, duration, _ = circle_lap()
    assert lap_samples(car[:5], loc[:5], T0.isoformat(), duration) is None

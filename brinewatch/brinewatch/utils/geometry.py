"""Small geometry helpers used across planners and backends."""
from __future__ import annotations

import math
from typing import Iterator, List, Tuple

import numpy as np


def wrap_angle(a: float) -> float:
    """Wrap an angle in radians to (-pi, pi]."""
    return math.atan2(math.sin(a), math.cos(a))


def heading_to(from_xy: Tuple[float, float], to_xy: Tuple[float, float]) -> float:
    """World-frame heading (radians, atan2 convention) from one point to another."""
    return math.atan2(to_xy[1] - from_xy[1], to_xy[0] - from_xy[0])


def dist2(a, b) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def dist3(a, b) -> float:
    return float(np.linalg.norm(np.asarray(b, dtype=float) - np.asarray(a, dtype=float)))


def expanding_square(center: Tuple[float, float], step: float, n_legs: int) -> Iterator[Tuple[float, float]]:
    """Yield 2-D waypoints of an expanding-square search pattern around ``center``.

    Standard SAR pattern: legs of length step, step, 2*step, 2*step, 3*step, ...
    rotating 90 degrees each leg.
    """
    x, y = center
    dx, dy = 1.0, 0.0
    leg = 0
    length = step
    yield (x, y)
    while leg < n_legs:
        x += dx * length
        y += dy * length
        yield (x, y)
        dx, dy = -dy, dx  # rotate 90 deg CCW
        leg += 1
        if leg % 2 == 0:
            length += step


def boustrophedon(
    x_min: float, x_max: float, y_min: float, y_max: float, spacing: float, along_x: bool = True
) -> List[Tuple[float, float]]:
    """Return the corner waypoints of a lawnmower pattern covering the box.

    Lines run along x (default) or along y, separated by ``spacing``.
    """
    pts: List[Tuple[float, float]] = []
    if along_x:
        ys = np.arange(y_min, y_max + 1e-9, spacing)
        for i, y in enumerate(ys):
            if i % 2 == 0:
                pts.append((x_min, float(y)))
                pts.append((x_max, float(y)))
            else:
                pts.append((x_max, float(y)))
                pts.append((x_min, float(y)))
    else:
        xs = np.arange(x_min, x_max + 1e-9, spacing)
        for i, x in enumerate(xs):
            if i % 2 == 0:
                pts.append((float(x), y_min))
                pts.append((float(x), y_max))
            else:
                pts.append((float(x), y_max))
                pts.append((float(x), y_min))
    return pts


def path_length(points: List[Tuple[float, float]]) -> float:
    total = 0.0
    for a, b in zip(points[:-1], points[1:]):
        total += dist2(a, b)
    return total

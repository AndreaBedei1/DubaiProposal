"""Collision-safe navigation around the known outfall structure.

A :class:`HazardField` models the outfall as a small set of 3-D capsules
(line segment + radius): the approach pipe, the exposed diffuser pipe and the
vertical risers. It is built from the LOCALIZED outfall position plus the
design chart geometry — never from simulator ground truth; the localization
error is absorbed by the clearance margin.

The field answers three navigation questions, all engine-free and
deterministic, so they are unit-tested without a simulator:

* ``clearance(p)`` / ``is_safe(p)`` — how far is a point from the nearest
  structure surface and from the seabed floor;
* ``project_to_safe(p)`` — the nearest point that respects the standoff and
  the minimum altitude (used to sanitize a commanded waypoint);
* ``safe_path(a, b)`` — a list of intermediate waypoints that gets from ``a``
  to ``b`` without ever breaching the standoff, by climbing over the structure
  or routing around it (used to turn a straight leg into a safe one).

Standoff clearance doubles as the inspection standoff: a survey ROV inspects
at a controlled distance, it does not touch the hardware.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence, Tuple

import numpy as np


def _seg_distance(p: np.ndarray, a: np.ndarray, b: np.ndarray) -> float:
    """Euclidean distance from point ``p`` to segment ``a``-``b``."""
    ab = b - a
    denom = float(ab @ ab)
    if denom < 1e-12:
        return float(np.linalg.norm(p - a))
    t = float((p - a) @ ab) / denom
    t = max(0.0, min(1.0, t))
    return float(np.linalg.norm(p - (a + t * ab)))


@dataclass
class Capsule:
    """A line segment ``p0``-``p1`` swept by a sphere of ``radius``."""

    p0: np.ndarray
    p1: np.ndarray
    radius: float

    def surface_distance(self, p: np.ndarray) -> float:
        """Distance to the capsule SURFACE (negative if inside)."""
        return _seg_distance(np.asarray(p, float),
                             np.asarray(self.p0, float),
                             np.asarray(self.p1, float)) - self.radius


@dataclass
class SafeNavConfig:
    clearance_m: float = 2.0        # standoff from the structure surface
    min_altitude_m: float = 1.0     # minimum height above the seabed
    detour_step_m: float = 1.5      # detour offset increment
    max_detour_m: float = 25.0      # give up beyond this lateral/vertical offset
    sample_step_m: float = 0.6      # segment clearance sampling resolution
    max_recursion: int = 5


class HazardField:
    def __init__(self, capsules: Sequence[Capsule],
                 seabed_fn: Optional[Callable] = None,
                 cfg: SafeNavConfig = SafeNavConfig()):
        self.capsules = list(capsules)
        self.seabed_fn = seabed_fn
        self.cfg = cfg
        # tallest structure reach above the local seabed (+ radius): a cruise
        # altitude above this clears every hazard by construction.
        self.max_reach = 0.0
        for c in self.capsules:
            for p in (np.asarray(c.p0, float), np.asarray(c.p1, float)):
                bed = float(seabed_fn(p[0], p[1])) if seabed_fn is not None else 0.0
                self.max_reach = max(self.max_reach, (p[2] - bed) + c.radius)

    # ------------------------------------------------------------------ #
    @classmethod
    def from_outfall(cls, estimate_xy: Tuple[float, float], axis_deg: float,
                     scene, seabed_fn: Callable,
                     cfg: SafeNavConfig = SafeNavConfig(),
                     origin_is_diffuser_start: bool = True) -> "HazardField":
        """Build the hazard capsules from the localized outfall + chart geometry.

        ``estimate_xy`` is the localized DIFFUSER-START position (the outfall
        origin); ``scene`` is an ``OutfallSceneConfig``. The pipe runs shoreward
        from the origin, the diffuser runs seaward, and each riser is a vertical
        capsule. Heights use ``seabed_fn`` (the mission's terrain model)."""
        ex, ey = float(estimate_xy[0]), float(estimate_xy[1])
        a = math.radians(axis_deg)
        u = np.array([math.cos(a), math.sin(a), 0.0])      # along axis (seaward)
        diff_len = scene.diffuser_length_m
        r_pipe = 0.5 * scene.pipe_diameter_m

        def at(s: float, h: float) -> np.ndarray:
            x, y = ex + s * u[0], ey + s * u[1]
            return np.array([x, y, float(seabed_fn(x, y)) + h])

        caps: List[Capsule] = []
        # approach pipe: shoreward from the origin (s < 0)
        caps.append(Capsule(at(-scene.pipe_length_m, 0.3 * scene.pipe_diameter_m),
                            at(0.0, 0.3 * scene.pipe_diameter_m),
                            r_pipe + 0.2))
        # exposed diffuser pipe: seaward along the diffuser span
        caps.append(Capsule(at(0.0, 0.5 * scene.pipe_diameter_m),
                            at(diff_len, 0.5 * scene.pipe_diameter_m),
                            r_pipe + 0.2))
        # risers (+ nozzles): vertical capsules at each port
        riser_reach = scene.riser_height_m + scene.nozzle_length_m * math.sin(
            math.radians(scene.nozzle_elevation_deg))
        r_riser = 0.5 * scene.riser_diameter_m + 0.5 * scene.nozzle_length_m
        for k in range(scene.n_risers):
            s = scene.diffuser_margin_m + k * scene.riser_spacing_m
            caps.append(Capsule(at(s, 0.0), at(s, riser_reach), r_riser))
        return cls(caps, seabed_fn, cfg)

    # ------------------------------------------------------------------ #
    def structure_clearance(self, p) -> float:
        """Distance from ``p`` to the nearest structure surface (neg = inside)."""
        p = np.asarray(p, float)
        if not self.capsules:
            return float("inf")
        return min(c.surface_distance(p) for c in self.capsules)

    def altitude(self, p) -> float:
        """Height of ``p`` above the seabed (inf if no terrain model)."""
        if self.seabed_fn is None:
            return float("inf")
        p = np.asarray(p, float)
        return float(p[2]) - float(self.seabed_fn(p[0], p[1]))

    def clearance(self, p) -> float:
        """Combined safety margin: min(structure standoff excess, altitude excess).

        Positive means both the structure standoff and the altitude floor are
        satisfied with room to spare."""
        s = self.structure_clearance(p) - self.cfg.clearance_m
        a = self.altitude(p) - self.cfg.min_altitude_m
        return min(s, a)

    def is_safe(self, p) -> bool:
        return self.clearance(p) >= 0.0

    # ------------------------------------------------------------------ #
    def project_to_safe(self, p) -> np.ndarray:
        """Nearest point (mostly vertical + radial nudge) that is safe."""
        p = np.asarray(p, float).copy()
        # lift above the altitude floor first
        if self.seabed_fn is not None:
            floor = float(self.seabed_fn(p[0], p[1])) + self.cfg.min_altitude_m
            if p[2] < floor:
                p[2] = floor
        # push radially out of any breached capsule, then climb if still short
        for _ in range(24):
            sc = self.structure_clearance(p)
            need = self.cfg.clearance_m - sc
            if need <= 1e-3:
                break
            c = min(self.capsules, key=lambda c: c.surface_distance(p))
            axis = np.asarray(c.p1, float) - np.asarray(c.p0, float)
            foot = self._closest_foot(p, np.asarray(c.p0, float), axis)
            radial = p - foot
            n = float(np.linalg.norm(radial))
            if n < 1e-6:                       # exactly on the axis: go up
                radial = np.array([0.0, 0.0, 1.0])
                n = 1.0
            p = p + (need + 0.05) * radial / n
        return p

    @staticmethod
    def _closest_foot(p: np.ndarray, a: np.ndarray, ab: np.ndarray) -> np.ndarray:
        denom = float(ab @ ab)
        if denom < 1e-12:
            return a
        t = max(0.0, min(1.0, float((p - a) @ ab) / denom))
        return a + t * ab

    # ------------------------------------------------------------------ #
    def segment_safe(self, a, b) -> bool:
        a = np.asarray(a, float)
        b = np.asarray(b, float)
        n = max(2, int(np.linalg.norm(b - a) / self.cfg.sample_step_m) + 1)
        for i in range(n + 1):
            if not self.is_safe(a + (b - a) * (i / n)):
                return False
        return True

    def _cruise_z(self, a: np.ndarray, b: np.ndarray) -> float:
        """A depth (world z) that clears every hazard along the a-b footprint by
        the standoff, following the highest seabed under the leg."""
        if self.seabed_fn is None:
            return max(float(a[2]), float(b[2]))
        n = max(2, int(np.linalg.norm(b[:2] - a[:2]) / self.cfg.sample_step_m) + 1)
        top_bed = max(float(self.seabed_fn(*(a[:2] + (b[:2] - a[:2]) * (i / n))))
                      for i in range(n + 1))
        return top_bed + self.max_reach + self.cfg.clearance_m + 1.0

    def safe_path(self, a, b) -> Tuple[List[np.ndarray], bool]:
        """Waypoints from ``a`` to ``b`` (excluding ``a``) that never breach the
        standoff. Returns (waypoints, fully_safe).

        If the start is itself unsafe the vehicle first escapes to a safe point.
        The primary maneuver is a smooth climb to a cruise altitude that clears
        the whole structure, a traverse over the top and a descent onto the
        (safe-projected) goal — the natural, video-friendly move for a top-down
        inspection. A single perpendicular go-around is tried as a fallback."""
        a = np.asarray(a, float)
        b = np.asarray(b, float)
        out: List[np.ndarray] = []
        if not self.is_safe(a):
            a = self.project_to_safe(a)
            out.append(a)
        b_safe = self.project_to_safe(b)

        if self.segment_safe(a, b_safe):
            return out + [b_safe], True

        # Primary: climb -> cruise over -> descend.
        zc = self._cruise_z(a, b_safe)
        w1 = np.array([a[0], a[1], zc])
        w2 = np.array([b_safe[0], b_safe[1], zc])
        if (self.segment_safe(a, w1) and self.segment_safe(w1, w2)
                and self.segment_safe(w2, b_safe)):
            return out + [w1, w2, b_safe], True

        # Fallback: lateral go-around at cruise altitude.
        horiz = b_safe[:2] - a[:2]
        hn = float(np.linalg.norm(horiz))
        perp = (np.array([-horiz[1], horiz[0]]) / hn
                if hn > 1e-6 else np.array([1.0, 0.0]))
        mid_xy = 0.5 * (a[:2] + b_safe[:2])
        steps = int(self.cfg.max_detour_m / self.cfg.detour_step_m)
        for i in range(1, steps + 1):
            off = i * self.cfg.detour_step_m
            for sgn in (+1.0, -1.0):
                m = np.array([mid_xy[0] + sgn * off * perp[0],
                              mid_xy[1] + sgn * off * perp[1], zc])
                w1 = np.array([a[0], a[1], zc])
                w3 = np.array([b_safe[0], b_safe[1], zc])
                legs = [(a, w1), (w1, m), (m, w3), (w3, b_safe)]
                if all(self.segment_safe(p, q) for p, q in legs):
                    return out + [w1, m, w3, b_safe], True
        return out + [b_safe], False

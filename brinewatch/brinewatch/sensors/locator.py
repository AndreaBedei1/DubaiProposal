"""Sonar-like diffuser locator.

Honesty note (see docs/assumptions.md): this is a *detection model*, not a
sonar signal simulation. When the vehicle is within ``max_range_m`` of the
true diffuser position, each ping detects it with probability
``detect_prob`` and returns range/bearing corrupted by Gaussian noise —
the information a forward-looking/scanning sonar plus an operator (or a
simple detector) would provide. In the HoloOcean backend the outfall is also
spawned as physical props, so the same geometry is visually and acoustically
plausible, but detection logic remains this model in both backends.
"""
from __future__ import annotations

import math
from typing import Optional, Tuple

import numpy as np

from ..utils.config import LocatorConfig
from ..utils.types import Detection, VehicleState


class DiffuserLocator:
    def __init__(self, cfg: LocatorConfig, true_xy: Tuple[float, float], seed: int = 0):
        self.cfg = cfg
        self.true_xy = (float(true_xy[0]), float(true_xy[1]))
        self._rng = np.random.default_rng(seed)

    def ping(self, state: VehicleState) -> Optional[Detection]:
        dx = self.true_xy[0] - state.x
        dy = self.true_xy[1] - state.y
        dist = math.hypot(dx, dy)
        if dist > self.cfg.max_range_m:
            return None
        if self._rng.random() > self.cfg.detect_prob:
            return None
        rng_meas = max(0.1, dist + self._rng.normal(0.0, self.cfg.range_sigma_m))
        bearing = math.atan2(dy, dx) + self._rng.normal(0.0, math.radians(self.cfg.bearing_sigma_deg))
        return Detection(
            t=state.t,
            range_m=rng_meas,
            bearing_rad=bearing,
            est_x=state.x + rng_meas * math.cos(bearing),
            est_y=state.y + rng_meas * math.sin(bearing),
        )

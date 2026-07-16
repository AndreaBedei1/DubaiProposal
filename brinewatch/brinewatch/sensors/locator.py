"""Diffuser localization sources.

Two explicit implementations with very different epistemic status:

- :class:`SyntheticDiffuserLocator` — an ORACLE-FED detection model: it knows
  the true outfall position and emits noisy range/bearing detections with a
  configurable detection probability. It exists so the fast kinematic
  benchmarks have a controlled, seedable LOCATE phase. It must NOT be used as
  the localization source in the official HoloOcean evidence runs (the
  mission config selects the source via ``LocatorConfig.mode``; the PFH 2026
  demo uses the sonar pipeline in ``brinewatch/perception/``).

- ``SonarDiffuserLocator`` (see ``brinewatch/perception/sonar_localizer.py``)
  — consumes actual HoloOcean ImagingSonar frames and the vehicle pose; it
  never receives the true outfall coordinates. Ground truth is only used
  *after* a mission, by the evaluator, to compute localization error.

Any fallback from sonar to synthetic must be explicit in configuration and
logged in the mission record — never silent (see docs/application/pfh2026).
"""
from __future__ import annotations

import math
from typing import Optional, Tuple

import numpy as np

from ..utils.config import LocatorConfig
from ..utils.types import Detection, VehicleState


class SyntheticDiffuserLocator:
    """Oracle-fed synthetic detection model (kinematic baselines ONLY).

    When the vehicle is within ``max_range_m`` of the true diffuser position,
    each ping detects it with probability ``detect_prob`` and returns
    range/bearing corrupted by Gaussian noise. This approximates the
    *information content* of a sonar contact without simulating acoustics."""

    name = "synthetic"

    def __init__(self, cfg: LocatorConfig, true_xy: Tuple[float, float], seed: int = 0):
        self.cfg = cfg
        self.true_xy = (float(true_xy[0]), float(true_xy[1]))
        self._rng = np.random.default_rng(seed)

    def observe(self, state: VehicleState, observation: Optional[dict] = None
                ) -> Optional[Detection]:
        """Uniform locator interface; the synthetic model ignores observations."""
        return self.ping(state)

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


# Backward-compatible alias (existing tests/imports); prefer the explicit name.
DiffuserLocator = SyntheticDiffuserLocator

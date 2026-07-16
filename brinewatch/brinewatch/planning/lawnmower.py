"""Fixed lawnmower (boustrophedon) survey — the baseline strategy.

Behaviour:
- On construction, precompute the full boustrophedon path over the survey box
  (``brinewatch.utils.geometry.boustrophedon``) with ``cfg.line_spacing_m``
  and ``cfg.along_x``; each 2-D corner becomes a
  ``Waypoint(x, y, seabed_fn(x, y) + survey.altitude_m)``.
- ``next_waypoint`` pops waypoints in order, ignoring the mapper (this is the
  non-adaptive baseline). Returns None when the pattern is exhausted.
- Budget-awareness: if the remaining budget is smaller than the straight-line
  distance to the next waypoint, still return it (the runner stops mid-leg);
  this keeps the pattern deterministic.
"""
from __future__ import annotations

from typing import Callable, List, Optional

from ..mapping.gp_mapper import GPMapper
from ..utils.config import LawnmowerConfig, SurveyConfig
from ..utils.geometry import boustrophedon
from ..utils.types import MissionBudget, VehicleState, Waypoint
from .base import Planner


class LawnmowerPlanner(Planner):
    name = "lawnmower"

    def __init__(
        self,
        survey: SurveyConfig,
        cfg: LawnmowerConfig,
        seabed_fn: Callable[[float, float], float],
    ):
        self.survey = survey
        self.cfg = cfg
        self.seabed_fn = seabed_fn
        corners = boustrophedon(
            survey.x_min,
            survey.x_max,
            survey.y_min,
            survey.y_max,
            cfg.line_spacing_m,
            along_x=cfg.along_x,
        )
        self._waypoints: List[Waypoint] = [
            Waypoint(x, y, float(seabed_fn(x, y)) + survey.altitude_m)
            for x, y in corners
        ]
        self._next_idx = 0

    def next_waypoint(
        self, state: VehicleState, mapper: GPMapper, budget: MissionBudget
    ) -> Optional[Waypoint]:
        if self._next_idx >= len(self._waypoints):
            return None
        wp = self._waypoints[self._next_idx]
        self._next_idx += 1
        return wp

"""Survey planner interface."""
from __future__ import annotations

import abc
from typing import Optional

from ..mapping.gp_mapper import GPMapper
from ..utils.types import MissionBudget, VehicleState, Waypoint


class Planner(abc.ABC):
    """A survey strategy. The mission runner calls :meth:`next_waypoint` each
    time the previous waypoint is reached; returning ``None`` ends the survey.

    Planners must be budget-aware: do not return waypoints that are pointless
    with the remaining budget (the runner will hard-stop at budget exhaustion
    regardless, mid-leg if necessary)."""

    name: str = "planner"

    @abc.abstractmethod
    def next_waypoint(
        self, state: VehicleState, mapper: GPMapper, budget: MissionBudget
    ) -> Optional[Waypoint]:
        """Return the next survey waypoint, or None when the plan is complete."""

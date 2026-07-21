"""Core value types shared across BrineWatch modules."""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np


@dataclass(frozen=True)
class Waypoint:
    """A 3-D navigation target in the world frame (z up, negative underwater)."""

    x: float
    y: float
    z: float
    tolerance: float = 1.5  # metres: waypoint considered reached within this radius

    @property
    def position(self) -> np.ndarray:
        return np.array([self.x, self.y, self.z], dtype=float)


@dataclass
class VehicleState:
    """Vehicle state as reported by a simulation backend at time ``t`` (sim seconds)."""

    t: float
    x: float
    y: float
    z: float
    roll: float = 0.0  # radians
    pitch: float = 0.0
    yaw: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0
    altitude: Optional[float] = None  # metres above seabed, if measured
    collided: bool = False  # backend-reported collision flag (HoloOcean)

    @property
    def position(self) -> np.ndarray:
        return np.array([self.x, self.y, self.z], dtype=float)

    def distance_to(self, wp: Waypoint) -> float:
        return float(np.linalg.norm(self.position - wp.position))


@dataclass(frozen=True)
class CTDSample:
    """One conductivity-temperature-depth measurement (already converted to
    practical salinity). Positions are the *believed* vehicle position at
    sampling time; noise on position is the backend's localization error."""

    t: float
    x: float
    y: float
    z: float
    salinity_psu: float
    temperature_c: float
    depth_m: float  # positive metres below surface as measured by pressure sensor

    @property
    def position(self) -> np.ndarray:
        return np.array([self.x, self.y, self.z], dtype=float)


@dataclass(frozen=True)
class Detection:
    """A diffuser detection from the sonar-like locator."""

    t: float
    range_m: float
    bearing_rad: float  # world-frame bearing from vehicle to target
    est_x: float  # estimated target position derived from range/bearing
    est_y: float


@dataclass
class MissionBudget:
    """Travel budget in metres — the proxy for battery/mission time.

    Both survey strategies consume from an identical budget, which is what
    makes the lawnmower-vs-adaptive comparison fair.
    """

    max_distance_m: float
    used_m: float = 0.0

    @property
    def remaining_m(self) -> float:
        return max(0.0, self.max_distance_m - self.used_m)

    @property
    def fraction_used(self) -> float:
        return self.used_m / self.max_distance_m if self.max_distance_m > 0 else 1.0

    @property
    def exhausted(self) -> bool:
        return self.used_m >= self.max_distance_m

    def would_exceed(self, metres: float) -> bool:
        """True if consuming ``metres`` more would pass the configured max."""
        return self.used_m + max(0.0, float(metres)) > self.max_distance_m

    def consume(self, metres: float) -> None:
        # Hard cap: the accounted distance never exceeds the configured budget
        # (a single control step must not overshoot the maximum). Any residual
        # beyond the cap is dropped from the accounting; both survey strategies
        # are clamped identically, so the equal-budget comparison stays fair.
        self.used_m = min(self.max_distance_m,
                          self.used_m + max(0.0, float(metres)))


class MissionPhase(enum.Enum):
    LOCATE = "locate"
    BASELINE = "baseline"
    SURVEY = "survey"
    DONE = "done"


@dataclass
class MissionResult:
    """Everything a mission produces, sufficient to rebuild maps and reports.

    ``budget_at_sample[i]`` is the budget (metres travelled) already consumed
    when ``samples[i]`` was taken; benchmarks slice on it to compare planners
    at equal budget checkpoints.
    """

    planner_name: str
    samples: List[CTDSample] = field(default_factory=list)
    budget_at_sample: List[float] = field(default_factory=list)
    trajectory: List[Tuple[float, float, float, float]] = field(default_factory=list)  # (t, x, y, z)
    detections: List[Detection] = field(default_factory=list)
    outfall_estimate: Optional[Tuple[float, float]] = None
    budget: Optional[MissionBudget] = None
    phase_history: List[Tuple[float, str]] = field(default_factory=list)  # (t, phase)
    wall_time_s: float = 0.0
    notes: List[str] = field(default_factory=list)

    def samples_within_budget(self, max_budget_m: float) -> List[CTDSample]:
        return [s for s, b in zip(self.samples, self.budget_at_sample) if b <= max_budget_m]

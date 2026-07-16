"""Sonar-based diffuser localization — NO ground-truth access.

Consumes :class:`SonarFrame` observations (image + synchronized pose) and
emits :class:`~brinewatch.utils.types.Detection` objects compatible with the
mission runner's LOCATE logic. World-frame estimates are formed from the
vehicle pose, the explicit sensor extrinsics and the detector's range/bearing
output — never from simulator ground truth. Clutter is rejected by requiring
spatial consistency: a detection is emitted only when the new world estimate
agrees (within ``cluster_radius_m``) with the running consensus of previous
estimates, so isolated rocks or speckle hits do not confirm an outfall.

Ground truth is used only AFTER a mission, by the evaluator, to score the
localization error of the final estimate.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

from ..sensors.sonar_types import SonarFrame
from ..utils.types import Detection, VehicleState
from .sonar_diffuser_detector import DetectorConfig, SonarDiffuserDetector


@dataclass
class SonarLocalizerConfig:
    detector: DetectorConfig = field(default_factory=DetectorConfig)
    cluster_radius_m: float = 5.0  # consensus radius for world estimates
    min_hits_for_consensus: int = 2  # estimates needed before emitting detections
    max_buffer: int = 400  # cap on stored world estimates
    min_strength: float = 5.0  # contact strength gate (robust z units)


class SonarDiffuserLocator:
    """Locator implementation backed by real sonar frames."""

    name = "sonar"

    def __init__(self, cfg: SonarLocalizerConfig = SonarLocalizerConfig()):
        self.cfg = cfg
        self.detector = SonarDiffuserDetector(cfg.detector)
        self._estimates: List[Tuple[float, float]] = []
        self.frames_seen = 0
        self.contacts_seen = 0

    # ------------------------------------------------------------------ #
    def observe(self, state: VehicleState, observation: Optional[dict]) -> Optional[Detection]:
        """Process one observation bundle; return a validated Detection or None."""
        if not observation:
            return None
        frame = observation.get("sonar")
        if frame is None:
            return None
        return self.update(frame)

    def update(self, frame: SonarFrame) -> Optional[Detection]:
        self.frames_seen += 1
        contacts = self.detector.detect(frame)
        best: Optional[Detection] = None
        for contact in contacts:
            if contact.strength < self.cfg.min_strength:
                continue
            self.contacts_seen += 1
            est = self._to_world(frame, contact.range_m, contact.bearing_rad)
            self._push(est)
            if self._consistent(est):
                bearing_world = float(frame.world_bearing(contact.centroid_col))
                det = Detection(
                    t=frame.t,
                    range_m=contact.range_m,
                    bearing_rad=bearing_world,
                    est_x=est[0],
                    est_y=est[1],
                )
                if best is None:
                    best = det
        return best

    # ------------------------------------------------------------------ #
    @property
    def consensus(self) -> Optional[Tuple[float, float]]:
        """Robust (median) world estimate from all buffered contacts."""
        if len(self._estimates) < self.cfg.min_hits_for_consensus:
            return None
        arr = np.asarray(self._estimates, dtype=float)
        return (float(np.median(arr[:, 0])), float(np.median(arr[:, 1])))

    def _to_world(self, frame: SonarFrame, range_m: float, bearing_sensor: float
                  ) -> Tuple[float, float]:
        yaw = frame.vehicle_rpy[2] + frame.extrinsics.yaw_offset_rad
        bearing_world = yaw + bearing_sensor
        x0 = frame.vehicle_xyz[0] + frame.extrinsics.forward_offset_m * math.cos(yaw)
        y0 = frame.vehicle_xyz[1] + frame.extrinsics.forward_offset_m * math.sin(yaw)
        return (x0 + range_m * math.cos(bearing_world),
                y0 + range_m * math.sin(bearing_world))

    def _push(self, est: Tuple[float, float]) -> None:
        self._estimates.append(est)
        if len(self._estimates) > self.cfg.max_buffer:
            self._estimates = self._estimates[-self.cfg.max_buffer:]

    def _consistent(self, est: Tuple[float, float]) -> bool:
        consensus = self.consensus
        if consensus is None:
            return False  # need corroboration before trusting any single hit
        return math.hypot(est[0] - consensus[0], est[1] - consensus[1]) \
            <= self.cfg.cluster_radius_m

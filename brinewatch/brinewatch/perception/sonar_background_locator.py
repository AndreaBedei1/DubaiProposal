"""Background-subtraction sonar localizer for the actual spawned outfall.

Real-survey change-detection analogue: a pre-installation baseline pass
records sonar frames at a set of survey poses; post-installation inspection
frames at the SAME poses have the native seabed/clutter subtracted, leaving
the newly installed structure's echoes. Residual contacts are projected to
world coordinates and combined with a robust weighted mode cluster.

This isolates the outfall from native level clutter that defeats a raw
detector (see docs/application/pfh2026/CUSTOM_LOCALIZATION_STUDY.md: raw gates
were clutter-limited to ~9 m; background subtraction reaches ~2.3 m over
independent acquisitions).

No ground truth is used: the locator consumes only sonar frames and vehicle
poses. The estimate can be scored against truth by the caller AFTER the run.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

from ..sensors.sonar_types import SonarFrame
from .sonar_diffuser_detector import DetectorConfig, SonarDiffuserDetector


@dataclass
class BackgroundLocatorConfig:
    detector: DetectorConfig = field(
        default_factory=lambda: DetectorConfig(min_range_m=6.0, z_threshold=3.5,
                                               min_area_bins=8))
    cluster_radius_m: float = 5.0
    min_contacts_for_consensus: int = 5
    prior_xy: Optional[Tuple[float, float]] = None
    prior_gate_m: float = 30.0     # reject residual contacts far from the prior


@dataclass
class BackgroundLocalization:
    estimate: Optional[Tuple[float, float]]
    n_contacts: int
    core_size: int
    aspect_span_deg: float
    fallback: bool


class SonarBackgroundLocator:
    """Accumulates residual (foreground) sonar contacts and reports a
    robust world-frame consensus estimate of the spawned structure."""

    name = "sonar_background"

    def __init__(self, cfg: BackgroundLocatorConfig = BackgroundLocatorConfig()):
        self.cfg = cfg
        self.detector = SonarDiffuserDetector(cfg.detector)
        self._contacts: List[Tuple[float, float, float, float]] = []  # x,y,heading,strength
        self.frames_seen = 0

    # ------------------------------------------------------------------ #
    def ingest(self, background: SonarFrame, live: SonarFrame) -> int:
        """Subtract the pose-matched background from a live frame and add the
        residual contacts. ``background`` and ``live`` must share the geometry
        (same range/azimuth extents) and be captured at the same pose; the
        live frame's pose is used for world projection. Returns the number of
        residual contacts added."""
        self.frames_seen += 1
        residual_img = np.clip(np.asarray(live.image, dtype=np.float32)
                               - np.asarray(background.image, dtype=np.float32),
                               0.0, None)
        residual = SonarFrame(
            t=live.t, image=residual_img,
            range_min_m=live.range_min_m, range_max_m=live.range_max_m,
            azimuth_fov_deg=live.azimuth_fov_deg,
            elevation_fov_deg=live.elevation_fov_deg,
            vehicle_xyz=live.vehicle_xyz, vehicle_rpy=live.vehicle_rpy,
            extrinsics=live.extrinsics)
        added = 0
        heading = live.vehicle_rpy[2] + live.extrinsics.yaw_offset_rad
        for c in self.detector.detect(residual):
            bearing = heading + float(residual.bearing_of_col(c.centroid_col))
            ex = live.vehicle_xyz[0] + c.range_m * math.cos(bearing)
            ey = live.vehicle_xyz[1] + c.range_m * math.sin(bearing)
            if self.cfg.prior_xy is not None:
                if math.hypot(ex - self.cfg.prior_xy[0],
                              ey - self.cfg.prior_xy[1]) > self.cfg.prior_gate_m:
                    continue
            self._contacts.append((ex, ey, heading, c.strength))
            added += 1
        return added

    # ------------------------------------------------------------------ #
    def localize(self) -> BackgroundLocalization:
        n = len(self._contacts)
        if n < self.cfg.min_contacts_for_consensus:
            return BackgroundLocalization(None, n, 0, 0.0, fallback=True)
        pts = np.array([(c[0], c[1]) for c in self._contacts], dtype=float)
        r2 = self.cfg.cluster_radius_m ** 2
        d2 = ((pts[:, None, :] - pts[None, :, :]) ** 2).sum(-1)
        counts = (d2 < r2).sum(1)
        seed = int(np.argmax(counts))
        core_mask = d2[seed] < r2
        core = pts[core_mask]
        est = core.mean(axis=0)
        headings = [self._contacts[i][2] for i in np.nonzero(core_mask)[0]]
        aspect = math.degrees(max(headings) - min(headings)) if headings else 0.0
        return BackgroundLocalization(
            estimate=(float(est[0]), float(est[1])),
            n_contacts=n, core_size=int(core_mask.sum()),
            aspect_span_deg=round(aspect, 1), fallback=False)

    @property
    def consensus(self) -> Optional[Tuple[float, float]]:
        return self.localize().estimate

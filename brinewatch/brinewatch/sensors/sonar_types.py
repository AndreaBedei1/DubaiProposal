"""Typed sonar observations shared by the backend, recorder and detector.

A :class:`SonarFrame` is a single range-azimuth intensity image from the
official HoloOcean ImagingSonar, stamped with the vehicle pose at the same
tick and the (explicit) sensor extrinsics. Everything downstream — recording,
replay, detection, localization — consumes only this structure, so the
detector can be developed and tested offline from recorded frames without a
simulator, and later fed from a physical sonar with the same geometry.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple

import numpy as np


@dataclass(frozen=True)
class SonarExtrinsics:
    """Mounting of the sonar relative to the vehicle body frame."""

    yaw_offset_rad: float = 0.0  # boresight vs vehicle nose (+CCW)
    forward_offset_m: float = 0.0  # along-body offset of the acoustic centre


@dataclass(frozen=True)
class SonarFrame:
    """One ImagingSonar image plus the synchronized vehicle pose.

    ``image``: (n_range, n_azimuth) float32; row 0 = RangeMin.
    Azimuth columns span [-azimuth_fov/2, +azimuth_fov/2] degrees across the
    image width (verified against HoloOcean output in the visibility gate).
    """

    t: float
    image: np.ndarray
    range_min_m: float
    range_max_m: float
    azimuth_fov_deg: float
    elevation_fov_deg: float
    vehicle_xyz: Tuple[float, float, float]
    vehicle_rpy: Tuple[float, float, float]  # radians
    extrinsics: SonarExtrinsics = field(default_factory=SonarExtrinsics)

    @property
    def n_range(self) -> int:
        return int(self.image.shape[0])

    @property
    def n_azimuth(self) -> int:
        return int(self.image.shape[1])

    def range_of_row(self, row) -> np.ndarray:
        """Metres at the centre of range bin(s) ``row``."""
        frac = (np.asarray(row, dtype=float) + 0.5) / self.n_range
        return self.range_min_m + frac * (self.range_max_m - self.range_min_m)

    def bearing_of_col(self, col) -> np.ndarray:
        """Sensor-frame bearing (radians, +CCW) of azimuth bin(s) ``col``.

        Column 0 is the +FOV/2 edge and the last column is -FOV/2: HoloOcean
        image columns run right-to-left in bearing (verified empirically in
        the visibility gate — a target left of the boresight brightens the
        high-column half)."""
        frac = (np.asarray(col, dtype=float) + 0.5) / self.n_azimuth
        return np.deg2rad((0.5 - frac) * self.azimuth_fov_deg)

    def world_bearing(self, col) -> np.ndarray:
        """World-frame bearing of azimuth bin(s), using pose + extrinsics."""
        yaw = self.vehicle_rpy[2] + self.extrinsics.yaw_offset_rad
        return yaw + self.bearing_of_col(col)

    def to_meta(self) -> dict:
        return {
            "t": self.t,
            "range_min_m": self.range_min_m,
            "range_max_m": self.range_max_m,
            "azimuth_fov_deg": self.azimuth_fov_deg,
            "elevation_fov_deg": self.elevation_fov_deg,
            "vehicle_xyz": list(self.vehicle_xyz),
            "vehicle_rpy": list(self.vehicle_rpy),
            "yaw_offset_rad": self.extrinsics.yaw_offset_rad,
            "forward_offset_m": self.extrinsics.forward_offset_m,
            "shape": list(self.image.shape),
        }

    @staticmethod
    def from_meta(image: np.ndarray, meta: dict) -> "SonarFrame":
        return SonarFrame(
            t=float(meta["t"]),
            image=np.asarray(image, dtype=np.float32),
            range_min_m=float(meta["range_min_m"]),
            range_max_m=float(meta["range_max_m"]),
            azimuth_fov_deg=float(meta["azimuth_fov_deg"]),
            elevation_fov_deg=float(meta["elevation_fov_deg"]),
            vehicle_xyz=tuple(meta["vehicle_xyz"]),
            vehicle_rpy=tuple(meta["vehicle_rpy"]),
            extrinsics=SonarExtrinsics(
                yaw_offset_rad=float(meta.get("yaw_offset_rad", 0.0)),
                forward_offset_m=float(meta.get("forward_offset_m", 0.0)),
            ),
        )

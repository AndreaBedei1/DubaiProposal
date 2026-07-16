"""Terrain height models built from range-finder soundings.

Pure math (no simulator imports): a :class:`TerrainMap` interpolates seabed
height from a grid of measured soundings, fits a reference plane for the
analytic plume model, and reports local slope for placing pipe segments
flush with the bottom.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Tuple, Union

import numpy as np
from scipy.interpolate import RegularGridInterpolator


@dataclass(frozen=True)
class PlaneFit:
    z0: float
    slope_x: float
    slope_y: float
    rmse_m: float

    def z(self, x, y):
        return self.z0 + self.slope_x * np.asarray(x) + self.slope_y * np.asarray(y)


class TerrainMap:
    """Bilinear seabed-height map over a rectangular sounding grid."""

    def __init__(self, xs: np.ndarray, ys: np.ndarray, bed_z: np.ndarray):
        xs = np.asarray(xs, dtype=float)
        ys = np.asarray(ys, dtype=float)
        bed = np.asarray(bed_z, dtype=float)
        if bed.shape != (len(ys), len(xs)):
            raise ValueError(f"bed_z shape {bed.shape} != (len(ys), len(xs))")
        if np.isnan(bed).any():
            bed = _fill_nan_nearest(bed)
        self.xs, self.ys, self.bed = xs, ys, bed
        self._interp = RegularGridInterpolator(
            (ys, xs), bed, bounds_error=False, fill_value=None
        )

    # ------------------------------------------------------------------ #
    @staticmethod
    def from_npz(path: Union[str, Path]) -> "TerrainMap":
        data = np.load(path)
        return TerrainMap(data["xs"], data["ys"], data["bed_z"])

    def save_npz(self, path: Union[str, Path]) -> None:
        np.savez(path, xs=self.xs, ys=self.ys, bed_z=self.bed)

    # ------------------------------------------------------------------ #
    def z(self, x, y):
        """Seabed z at (x, y) — clamped extrapolation outside the grid."""
        pts = np.column_stack([np.atleast_1d(np.asarray(y, dtype=float)),
                               np.atleast_1d(np.asarray(x, dtype=float))])
        out = self._interp(pts)
        return float(out[0]) if np.isscalar(x) or np.asarray(x).ndim == 0 else out

    def slope_between(self, p0: Tuple[float, float], p1: Tuple[float, float]) -> float:
        """Pitch angle (radians) of the seabed line from p0 to p1."""
        dz = self.z(p1[0], p1[1]) - self.z(p0[0], p0[1])
        dh = float(np.hypot(p1[0] - p0[0], p1[1] - p0[1]))
        return float(np.arctan2(dz, dh)) if dh > 1e-6 else 0.0

    def fit_plane(self) -> PlaneFit:
        """Least-squares plane through the soundings (for the plume model)."""
        X, Y = np.meshgrid(self.xs, self.ys)
        A = np.column_stack([np.ones(X.size), X.ravel(), Y.ravel()])
        coef, *_ = np.linalg.lstsq(A, self.bed.ravel(), rcond=None)
        resid = self.bed.ravel() - A @ coef
        return PlaneFit(z0=float(coef[0]), slope_x=float(coef[1]),
                        slope_y=float(coef[2]), rmse_m=float(np.sqrt(np.mean(resid ** 2))))


def _fill_nan_nearest(grid: np.ndarray) -> np.ndarray:
    """Replace NaN soundings with the nearest valid value (small gaps only)."""
    from scipy import ndimage

    mask = np.isnan(grid)
    if not mask.any():
        return grid
    if mask.all():
        raise ValueError("terrain grid has no valid soundings")
    idx = ndimage.distance_transform_edt(mask, return_distances=False,
                                         return_indices=True)
    return grid[tuple(idx)]

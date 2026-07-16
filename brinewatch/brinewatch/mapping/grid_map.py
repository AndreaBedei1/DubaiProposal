"""Evaluation grids: the near-bottom layer where the brine plume lives."""
from __future__ import annotations

from typing import Callable, Optional, Tuple

import numpy as np

from ..utils.config import SurveyConfig


class EvalGrid:
    """A 2.5-D grid: regular (x, y) lattice over the survey box, with
    z = seabed(x, y) + altitude. Used for reconstruction, metrics, compliance
    and plotting. ``points`` is (N, 3) in row-major (y, x) order so values can
    be reshaped to images with :meth:`reshape`."""

    def __init__(
        self,
        survey: SurveyConfig,
        seabed_fn: Callable[[np.ndarray, np.ndarray], np.ndarray],
        altitude_m: float,
        resolution_m: Optional[float] = None,
    ):
        res = resolution_m if resolution_m is not None else survey.grid_resolution_m
        self.xs = np.arange(survey.x_min, survey.x_max + 1e-9, res)
        self.ys = np.arange(survey.y_min, survey.y_max + 1e-9, res)
        self.X, self.Y = np.meshgrid(self.xs, self.ys)  # shape (ny, nx)
        self.Z = np.asarray(seabed_fn(self.X, self.Y)) + altitude_m
        self.altitude_m = altitude_m
        self.resolution_m = res

    @property
    def shape(self) -> Tuple[int, int]:
        return self.X.shape

    @property
    def points(self) -> np.ndarray:
        return np.column_stack([self.X.ravel(), self.Y.ravel(), self.Z.ravel()])

    def reshape(self, values: np.ndarray) -> np.ndarray:
        return np.asarray(values).reshape(self.shape)

    def distance_from(self, cx: float, cy: float) -> np.ndarray:
        """Horizontal distance of every grid node from (cx, cy), flattened (N,)."""
        return np.hypot(self.X.ravel() - cx, self.Y.ravel() - cy)

    def mask_outside_radius(self, cx: float, cy: float, radius_m: float) -> np.ndarray:
        """Boolean (N,) mask of nodes strictly beyond ``radius_m`` from (cx, cy)."""
        return self.distance_from(cx, cy) > radius_m

    def cell_area_m2(self) -> float:
        return self.resolution_m ** 2

"""Reconstruction-quality metrics on the near-bottom evaluation grid.

All metrics compare a GP reconstruction against the analytic ground truth on
an :class:`~brinewatch.mapping.grid_map.EvalGrid` (values are flattened (N,)
arrays aligned with ``grid.points``):

- ``rmse_all``: RMSE over the whole grid.
- ``rmse_plume``: RMSE restricted to cells where the true anomaly above
  ambient exceeds ``plume_eps_psu`` (accuracy where it matters). The anomaly
  is evaluated from the plume model at ``truth_time_s``; without a plume
  model it falls back to ``truth - truth.min()``. NaN when no cell qualifies.
- ``mae_all``: mean absolute error over the whole grid.
- ``boundary_f1`` / ``boundary_iou``: F1 and IoU between the boolean masks
  ``truth > threshold_psu`` and ``mean > threshold_psu`` — how well the
  compliance isohaline is localized. If the true mask is empty, F1/IoU are
  1.0 when the predicted mask is also empty, else 0.0.
- ``coverage_frac``: fraction of grid nodes within ``coverage_radius_m``
  (horizontal) of at least one sample position (0.0 with no samples).
- ``n_samples``: number of samples used.
- ``in_plume_frac``: fraction of samples taken where the true anomaly at the
  sample position/time exceeds ``plume_eps_psu`` (were we sampling signal or
  blue water?). Requires the plume model: NaN when ``plume`` is None (or
  when there are no samples).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
from scipy.spatial import cKDTree

from ..mapping.grid_map import EvalGrid
from ..plume.model import BrinePlume
from ..utils.types import CTDSample


@dataclass
class MetricsResult:
    rmse_all: float
    rmse_plume: float
    mae_all: float
    boundary_f1: float
    boundary_iou: float
    coverage_frac: float
    n_samples: int
    in_plume_frac: float


def compute_metrics(
    mean: np.ndarray,
    truth: np.ndarray,
    grid: EvalGrid,
    samples: List[CTDSample],
    threshold_psu: float,
    plume: Optional[BrinePlume] = None,
    plume_eps_psu: float = 0.5,
    coverage_radius_m: float = 8.0,
    truth_time_s: float = 0.0,
) -> MetricsResult:
    """Compute all metrics; see module docstring for definitions."""
    mean = np.asarray(mean, dtype=float).ravel()
    truth = np.asarray(truth, dtype=float).ravel()
    n_cells = grid.X.size
    if mean.size != n_cells or truth.size != n_cells:
        raise ValueError(
            f"mean/truth must be flattened over the grid ({n_cells} cells), "
            f"got {mean.size} and {truth.size}"
        )

    err = mean - truth
    rmse_all = float(np.sqrt(np.mean(err ** 2)))
    mae_all = float(np.mean(np.abs(err)))

    plume_mask = _true_anomaly(truth, grid, plume, truth_time_s) > plume_eps_psu
    if plume_mask.any():
        rmse_plume = float(np.sqrt(np.mean(err[plume_mask] ** 2)))
    else:
        rmse_plume = float("nan")

    boundary_f1, boundary_iou = _boundary_scores(truth > threshold_psu, mean > threshold_psu)

    return MetricsResult(
        rmse_all=rmse_all,
        rmse_plume=rmse_plume,
        mae_all=mae_all,
        boundary_f1=boundary_f1,
        boundary_iou=boundary_iou,
        coverage_frac=_coverage_frac(grid, samples, coverage_radius_m),
        n_samples=len(samples),
        in_plume_frac=_in_plume_frac(samples, plume, plume_eps_psu),
    )


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _true_anomaly(
    truth: np.ndarray, grid: EvalGrid, plume: Optional[BrinePlume], truth_time_s: float
) -> np.ndarray:
    """True salinity anomaly above ambient at every grid node, flattened (N,)."""
    if plume is not None:
        return np.asarray(
            plume.salinity_anomaly(grid.X.ravel(), grid.Y.ravel(), grid.Z.ravel(), truth_time_s),
            dtype=float,
        )
    return truth - float(np.min(truth))


def _boundary_scores(true_mask: np.ndarray, pred_mask: np.ndarray) -> Tuple[float, float]:
    """F1 and IoU between two boolean masks, with the empty-truth convention."""
    if not true_mask.any():
        score = 1.0 if not pred_mask.any() else 0.0
        return score, score
    tp = int(np.count_nonzero(true_mask & pred_mask))
    fp = int(np.count_nonzero(~true_mask & pred_mask))
    fn = int(np.count_nonzero(true_mask & ~pred_mask))
    f1 = 2.0 * tp / (2.0 * tp + fp + fn)
    iou = tp / float(np.count_nonzero(true_mask | pred_mask))
    return float(f1), float(iou)


def _coverage_frac(grid: EvalGrid, samples: List[CTDSample], coverage_radius_m: float) -> float:
    """Fraction of grid nodes within ``coverage_radius_m`` (x, y) of a sample."""
    if not samples:
        return 0.0
    sample_xy = np.array([[s.x, s.y] for s in samples], dtype=float)
    grid_xy = np.column_stack([grid.X.ravel(), grid.Y.ravel()])
    dist, _ = cKDTree(sample_xy).query(grid_xy, k=1)
    return float(np.mean(dist <= coverage_radius_m))


def _in_plume_frac(
    samples: List[CTDSample], plume: Optional[BrinePlume], plume_eps_psu: float
) -> float:
    """Fraction of samples whose true anomaly (at their own time) exceeds eps."""
    if plume is None or not samples:
        return float("nan")
    xs = np.array([s.x for s in samples], dtype=float)
    ys = np.array([s.y for s in samples], dtype=float)
    zs = np.array([s.z for s in samples], dtype=float)
    ts = np.array([s.t for s in samples], dtype=float)
    anomaly = np.asarray(plume.salinity_anomaly(xs, ys, zs, ts), dtype=float)
    return float(np.mean(anomaly > plume_eps_psu))

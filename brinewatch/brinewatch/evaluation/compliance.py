"""Mixing-zone compliance verdict.

Rule (configurable, docs/assumptions.md): outside the mixing zone —
horizontal distance > ``cfg.mixing_zone_radius_m`` from the outfall — the
near-bottom salinity must not exceed
``ambient_bottom_psu * (1 + cfg.threshold_increment_pct / 100)``.

``evaluate_compliance`` works on a reconstruction (mean, std) over an
EvalGrid; ``std=None`` (or zeros) evaluates a noiseless field (ground truth).
Definitions:
- ``compliant``: no grid node outside the zone has ``mean > threshold``.
- ``max_exceedance_psu``: max(mean - threshold) outside the zone (can be
  negative when compliant — it is then the margin).
- ``worst_point``: (x, y) of the node attaining the max.
- ``prob_exceed_max``: with a GP std, max over outside nodes of
  P(salinity > threshold) = Phi((mean - threshold)/std); with std=None use
  the indicator (0/1). Cells with std == 0 also use the indicator. Report
  this as the uncertainty-aware verdict.
- ``n_cells_exceeding``: count of outside nodes with mean > threshold.

Degenerate case: if the mixing zone swallows the whole grid (no outside
node) the field is trivially compliant; ``max_exceedance_psu`` and
``worst_point`` are NaN and ``prob_exceed_max`` is 0.0.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np
from scipy.special import ndtr

from ..mapping.grid_map import EvalGrid
from ..utils.config import ComplianceConfig


@dataclass
class ComplianceVerdict:
    compliant: bool  # legacy binary verdict (kept for backward-compatible metrics)
    threshold_psu: float
    max_exceedance_psu: float
    worst_point: Tuple[float, float]
    prob_exceed_max: float
    n_cells_exceeding: int
    mixing_zone_radius_m: float
    # Max GP posterior std outside the zone (NaN for noiseless/GT fields):
    # the three-state screening needs it to tell CLEAR from REVIEW.
    max_std_outside_psu: float = float("nan")

    @property
    def label(self) -> str:
        return "PASS" if self.compliant else "FAIL"


def evaluate_compliance(
    mean: np.ndarray,
    std: Optional[np.ndarray],
    grid: EvalGrid,
    outfall_xy: Tuple[float, float],
    cfg: ComplianceConfig,
    ambient_bottom_psu: float,
) -> ComplianceVerdict:
    """Evaluate the mixing-zone rule on a (possibly uncertain) salinity field."""
    mean = np.asarray(mean, dtype=float).ravel()
    n_cells = grid.X.size
    if mean.size != n_cells:
        raise ValueError(f"mean must be flattened over the grid ({n_cells} cells), got {mean.size}")

    threshold = float(ambient_bottom_psu) * (1.0 + cfg.threshold_increment_pct / 100.0)
    outside = grid.mask_outside_radius(outfall_xy[0], outfall_xy[1], cfg.mixing_zone_radius_m)

    if not outside.any():
        return ComplianceVerdict(
            compliant=True,
            threshold_psu=threshold,
            max_exceedance_psu=float("nan"),
            worst_point=(float("nan"), float("nan")),
            prob_exceed_max=0.0,
            n_cells_exceeding=0,
            mixing_zone_radius_m=cfg.mixing_zone_radius_m,
        )

    exceedance = np.where(outside, mean - threshold, -np.inf)
    worst_idx = int(np.argmax(exceedance))
    n_exceeding = int(np.count_nonzero(outside & (mean > threshold)))

    prob = _prob_exceed(mean, std, threshold)
    prob_exceed_max = float(np.max(np.where(outside, prob, 0.0)))

    max_std_outside = float("nan")
    if std is not None:
        std_arr = np.asarray(std, dtype=float).ravel()
        if std_arr.size == mean.size:
            max_std_outside = float(np.max(np.where(outside, std_arr, 0.0)))

    return ComplianceVerdict(
        compliant=n_exceeding == 0,
        threshold_psu=threshold,
        max_exceedance_psu=float(exceedance[worst_idx]),
        worst_point=(float(grid.X.ravel()[worst_idx]), float(grid.Y.ravel()[worst_idx])),
        prob_exceed_max=prob_exceed_max,
        n_cells_exceeding=n_exceeding,
        mixing_zone_radius_m=cfg.mixing_zone_radius_m,
        max_std_outside_psu=max_std_outside,
    )


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _prob_exceed(mean: np.ndarray, std: Optional[np.ndarray], threshold: float) -> np.ndarray:
    """Per-cell P(salinity > threshold): normal CDF where std > 0, else 0/1."""
    indicator = (mean > threshold).astype(float)
    if std is None:
        return indicator
    std = np.asarray(std, dtype=float).ravel()
    if std.size != mean.size:
        raise ValueError(f"std must match mean length {mean.size}, got {std.size}")
    positive = std > 0.0
    if not positive.any():
        return indicator
    prob = indicator.copy()
    prob[positive] = ndtr((mean[positive] - threshold) / std[positive])
    return prob

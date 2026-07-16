"""Matplotlib figures for missions and benchmarks (Agg backend, save-to-file).

Common conventions:
- The Agg backend is selected before pyplot import; nothing is ever shown.
- All functions save a PNG to ``path`` (parents created) and return ``path``.
- Fields passed as flattened (N,) arrays aligned with ``grid.points`` are
  reshaped with ``grid.reshape`` and drawn over the ``grid.xs`` / ``grid.ys``
  extents.
- The outfall is marked with a triangle, the mixing zone as a dashed circle,
  the compliance threshold as a labelled contour line.

Functions:
- ``plot_truth_vs_reconstruction``: 1x3 panel — ground truth, GP mean (with
  sample points and vehicle trajectory overlaid), GP std. Shared salinity
  colorbar for truth/mean; separate one for std.
- ``plot_learning_curves``: for each metric key, error/score vs budget
  checkpoint per planner (mean line + shaded +-1 std band across seeds).
  ``records`` are the flat dicts produced by evaluation.benchmark.
- ``plot_compliance_map``: exceedance map (mean - threshold, diverging cmap
  centred at 0) with the mixing-zone circle and worst point marked.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402  (backend must be set first)
import numpy as np  # noqa: E402
from matplotlib.patches import Circle  # noqa: E402

from ..mapping.grid_map import EvalGrid  # noqa: E402
from ..utils.types import CTDSample  # noqa: E402

_DPI = 130


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #
def _prepare_path(path: Union[str, Path]) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    return out


def _extent(grid: EvalGrid) -> Tuple[float, float, float, float]:
    return (float(grid.xs[0]), float(grid.xs[-1]), float(grid.ys[0]), float(grid.ys[-1]))


def _draw_field(
    ax: plt.Axes,
    grid: EvalGrid,
    field: np.ndarray,
    cmap: str,
    vmin: Optional[float] = None,
    vmax: Optional[float] = None,
):
    """imshow a flattened field on ``ax`` with metric axes; return the image."""
    img = ax.imshow(
        grid.reshape(field),
        origin="lower",
        extent=_extent(grid),
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        aspect="equal",
        interpolation="nearest",
    )
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    return img


def _draw_outfall_and_zone(
    ax: plt.Axes,
    outfall_xy: Tuple[float, float],
    mixing_radius_m: float,
    with_labels: bool = False,
) -> None:
    """Mark the outfall (triangle) and the mixing-zone circle (dashed)."""
    ax.plot(
        [outfall_xy[0]],
        [outfall_xy[1]],
        marker="^",
        markersize=10,
        color="white",
        markeredgecolor="black",
        linestyle="none",
        zorder=6,
        label="outfall" if with_labels else None,
    )
    circle = Circle(
        tuple(outfall_xy),
        mixing_radius_m,
        fill=False,
        edgecolor="black",
        linestyle="--",
        linewidth=1.3,
        zorder=5,
        label="mixing zone" if with_labels else None,
    )
    ax.add_patch(circle)


def _draw_threshold_contour(
    ax: plt.Axes, grid: EvalGrid, field: np.ndarray, threshold_psu: float, color: str = "black"
) -> None:
    """Labelled contour of the compliance threshold, skipped if out of range."""
    field2d = grid.reshape(field)
    if not (np.nanmin(field2d) < threshold_psu < np.nanmax(field2d)):
        return
    cs = ax.contour(grid.X, grid.Y, field2d, levels=[threshold_psu], colors=[color], linewidths=1.4)
    ax.clabel(cs, fmt=lambda _lvl: f"{threshold_psu:g} PSU", fontsize=8)


def _legend_if_any(ax: plt.Axes) -> None:
    handles, _labels = ax.get_legend_handles_labels()
    if handles:
        ax.legend(loc="upper right", fontsize=8, framealpha=0.85)


# --------------------------------------------------------------------------- #
# Figures
# --------------------------------------------------------------------------- #
def plot_truth_vs_reconstruction(
    grid: EvalGrid,
    truth: np.ndarray,
    mean: np.ndarray,
    std: np.ndarray,
    samples: List[CTDSample],
    trajectory: List[Tuple[float, float, float, float]],
    outfall_xy: Tuple[float, float],
    mixing_radius_m: float,
    threshold_psu: float,
    path: Union[str, Path],
    title: str = "",
) -> Path:
    """1x3 panel: ground truth, GP mean (with samples/trajectory), GP std."""
    out = _prepare_path(path)
    truth = np.asarray(truth, dtype=float)
    mean = np.asarray(mean, dtype=float)
    std = np.asarray(std, dtype=float)

    vmin = float(min(np.nanmin(truth), np.nanmin(mean)))
    vmax = float(max(np.nanmax(truth), np.nanmax(mean)))

    fig, (ax_truth, ax_mean, ax_std) = plt.subplots(1, 3, figsize=(16.0, 5.2), constrained_layout=True)

    im_truth = _draw_field(ax_truth, grid, truth, "viridis", vmin=vmin, vmax=vmax)
    ax_truth.set_title("Ground truth")
    _draw_threshold_contour(ax_truth, grid, truth, threshold_psu)
    _draw_outfall_and_zone(ax_truth, outfall_xy, mixing_radius_m)

    _draw_field(ax_mean, grid, mean, "viridis", vmin=vmin, vmax=vmax)
    ax_mean.set_title("GP mean")
    _draw_threshold_contour(ax_mean, grid, mean, threshold_psu)
    _draw_outfall_and_zone(ax_mean, outfall_xy, mixing_radius_m, with_labels=True)
    if trajectory:
        txy = np.asarray([(p[1], p[2]) for p in trajectory], dtype=float)
        ax_mean.plot(txy[:, 0], txy[:, 1], color="0.35", linewidth=0.9, alpha=0.85, zorder=3, label="trajectory")
    if samples:
        ax_mean.scatter(
            [s.x for s in samples],
            [s.y for s in samples],
            s=14,
            c="crimson",
            edgecolors="white",
            linewidths=0.4,
            zorder=4,
            label="samples",
        )
    _legend_if_any(ax_mean)

    im_std = _draw_field(ax_std, grid, std, "magma")
    ax_std.set_title("GP std")
    _draw_outfall_and_zone(ax_std, outfall_xy, mixing_radius_m)

    fig.colorbar(im_truth, ax=[ax_truth, ax_mean], label="Salinity (PSU)", shrink=0.9)
    fig.colorbar(im_std, ax=ax_std, label="Salinity std (PSU)", shrink=0.9)
    if title:
        fig.suptitle(title)
    fig.savefig(out, dpi=_DPI)
    plt.close(fig)
    return out


def plot_learning_curves(
    records: List[Dict[str, Any]],
    path: Union[str, Path],
    metrics: Sequence[str] = ("rmse_plume", "boundary_f1", "coverage_frac"),
) -> Path:
    """One subplot per metric: value vs budget metres, one line per planner.

    Lines are the mean across seeds at each budget checkpoint; the shaded band
    is +-1 std across seeds. Records missing a metric key are skipped for that
    subplot.
    """
    out = _prepare_path(path)
    planners = sorted({str(r["planner"]) for r in records if "planner" in r})
    colors = {p: f"C{i}" for i, p in enumerate(planners)}

    n = max(1, len(metrics))
    fig, axes = plt.subplots(1, n, figsize=(4.8 * n, 3.9), constrained_layout=True)
    axes = np.atleast_1d(axes)

    for ax, metric in zip(axes, metrics):
        for planner in planners:
            by_budget: Dict[float, List[float]] = {}
            for rec in records:
                if str(rec.get("planner")) != planner:
                    continue
                if metric not in rec or rec[metric] is None or "budget_m" not in rec:
                    continue
                key = round(float(rec["budget_m"]), 6)
                by_budget.setdefault(key, []).append(float(rec[metric]))
            if not by_budget:
                continue
            budgets = np.asarray(sorted(by_budget))
            means = np.asarray([np.mean(by_budget[b]) for b in budgets])
            stds = np.asarray([np.std(by_budget[b]) for b in budgets])
            ax.plot(budgets, means, marker="o", markersize=4, color=colors[planner], label=planner)
            ax.fill_between(budgets, means - stds, means + stds, color=colors[planner], alpha=0.18)
        ax.set_xlabel("Budget (m)")
        ax.set_ylabel(metric)
        ax.set_title(metric)
        ax.grid(True, alpha=0.3)
        _legend_if_any(ax)

    fig.savefig(out, dpi=_DPI)
    plt.close(fig)
    return out


def plot_compliance_map(
    grid: EvalGrid,
    mean: np.ndarray,
    threshold_psu: float,
    outfall_xy: Tuple[float, float],
    mixing_radius_m: float,
    path: Union[str, Path],
    worst_point: Optional[Tuple[float, float]] = None,
    title: str = "",
) -> Path:
    """Exceedance map (mean - threshold) on a diverging colormap centred at 0."""
    out = _prepare_path(path)
    exceedance = np.asarray(mean, dtype=float) - threshold_psu
    limit = float(max(np.nanmax(np.abs(exceedance)), 1e-9))

    fig, ax = plt.subplots(figsize=(7.4, 6.2), constrained_layout=True)
    img = _draw_field(ax, grid, exceedance, "RdBu_r", vmin=-limit, vmax=limit)
    fig.colorbar(img, ax=ax, label=f"Exceedance over {threshold_psu:g} PSU threshold (PSU)")

    _draw_threshold_contour(ax, grid, np.asarray(mean, dtype=float), threshold_psu)
    _draw_outfall_and_zone(ax, outfall_xy, mixing_radius_m, with_labels=True)
    if worst_point is not None:
        ax.plot(
            [worst_point[0]],
            [worst_point[1]],
            marker="X",
            markersize=11,
            color="yellow",
            markeredgecolor="black",
            linestyle="none",
            zorder=7,
            label="worst point",
        )
    _legend_if_any(ax)
    ax.set_title(title or "Mixing-zone compliance map")

    fig.savefig(out, dpi=_DPI)
    plt.close(fig)
    return out

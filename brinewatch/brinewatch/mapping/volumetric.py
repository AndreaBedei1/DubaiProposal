"""3-D volumetric brine-plume reconstruction (x-y-z), built on the same
anisotropic GP as the near-bottom map.

Dense brine sinks, so the plume is a near-bottom layer; a BlueROV2 samples it
at several altitudes above the seabed. This module reconstructs the salinity
field on a terrain-following x-y-z grid, extracts horizontal and vertical
slices and a configurable iso-surface, and estimates plume area (the
near-bottom compliance layer), volume and their uncertainty.

The analytic plume (``brinewatch.plume.model.BrinePlume``) is a documented
SIMULATION SURROGATE, not CFD ground truth; the reconstruction quality is
reported against it only for evaluation.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import numpy as np


@dataclass
class VolumetricConfig:
    nx: int = 32
    ny: int = 32
    nz: int = 14                 # altitude layers above the seabed
    z_above_bed_max_m: float = 8.0
    z_above_bed_min_m: float = 0.2
    margin_m: float = 1.0        # inset from the survey-box edges


class VolumetricGrid:
    """Terrain-following x-y-z grid over the survey box.

    Cells are indexed [ix, iy, iz]; z of a cell = local seabed(x,y) + altitude.
    The bottom altitude layer (iz=0) is the near-bottom compliance layer.
    """

    def __init__(self, survey, seabed_fn: Callable, cfg: VolumetricConfig = VolumetricConfig()):
        self.cfg = cfg
        m = cfg.margin_m
        self.xs = np.linspace(survey.x_min + m, survey.x_max - m, cfg.nx)
        self.ys = np.linspace(survey.y_min + m, survey.y_max - m, cfg.ny)
        self.alts = np.linspace(cfg.z_above_bed_min_m, cfg.z_above_bed_max_m, cfg.nz)
        self.X, self.Y, self.A = np.meshgrid(self.xs, self.ys, self.alts, indexing="ij")
        self.bed = np.asarray(seabed_fn(self.X[:, :, 0], self.Y[:, :, 0]), dtype=float)
        self.Z = self.bed[:, :, None] + self.A
        self.shape = self.X.shape
        self.dx = float(self.xs[1] - self.xs[0]) if cfg.nx > 1 else 1.0
        self.dy = float(self.ys[1] - self.ys[0]) if cfg.ny > 1 else 1.0
        self.dalt = float(self.alts[1] - self.alts[0]) if cfg.nz > 1 else 1.0

    @property
    def points(self) -> np.ndarray:
        return np.column_stack([self.X.ravel(), self.Y.ravel(), self.Z.ravel()])

    def reshape(self, v: np.ndarray) -> np.ndarray:
        return np.asarray(v).reshape(self.shape)


def reconstruct(mapper, grid: VolumetricGrid):
    """Predict GP mean and std over the volumetric grid; returns (mean, std)
    each shaped like the grid."""
    mean, std = mapper.predict(grid.points)
    return grid.reshape(mean), grid.reshape(std)


@dataclass
class VolumetricMetrics:
    threshold_psu: float
    plume_volume_m3: float
    plume_area_bottom_m2: float
    peak_salinity_psu: float
    mean_altitude_of_plume_m: float
    plume_top_height_m: float           # max altitude above bed with salinity >= threshold
    uncertain_volume_m3: float          # cells where |mean-thr| < std (verdict-ambiguous)
    mean_std_in_plume_psu: float
    n_plume_cells: int


def plume_body_mask(field: np.ndarray, threshold_psu: float) -> np.ndarray:
    """Largest connected above-threshold component (the physical plume body).

    The brine plume is a single connected body; isolated above-threshold cells
    in poorly-sampled regions are GP artefacts and are dropped. Falls back to
    the raw threshold mask if scipy is unavailable."""
    mask = field >= threshold_psu
    if not mask.any():
        return mask
    try:
        from scipy import ndimage
        lbl, n = ndimage.label(mask)
        if n <= 1:
            return mask
        sizes = ndimage.sum(mask, lbl, range(1, n + 1))
        return lbl == (int(np.argmax(sizes)) + 1)
    except Exception:
        return mask


def metrics(mean_vol: np.ndarray, std_vol: np.ndarray, grid: VolumetricGrid,
            threshold_psu: float) -> VolumetricMetrics:
    cell_vol = grid.dx * grid.dy * grid.dalt
    cell_area = grid.dx * grid.dy
    mask = plume_body_mask(mean_vol, threshold_psu)
    n = int(mask.sum())
    bottom = mask[:, :, 0]
    if n:
        alt_of_plume = float(grid.A[mask].mean())
        top = float(grid.A[mask].max())
        std_in = float(std_vol[mask].mean())
    else:
        alt_of_plume = top = std_in = 0.0
    uncertain = np.abs(mean_vol - threshold_psu) < std_vol
    return VolumetricMetrics(
        threshold_psu=round(threshold_psu, 3),
        plume_volume_m3=round(n * cell_vol, 1),
        plume_area_bottom_m2=round(int(bottom.sum()) * cell_area, 1),
        peak_salinity_psu=round(float(mean_vol.max()), 3),
        mean_altitude_of_plume_m=round(alt_of_plume, 2),
        plume_top_height_m=round(top, 2),
        uncertain_volume_m3=round(int(uncertain.sum()) * cell_vol, 1),
        mean_std_in_plume_psu=round(std_in, 3),
        n_plume_cells=n)


# --------------------------------------------------------------------------- #
# Figures (matplotlib only; no skimage/plotly dependency)
# --------------------------------------------------------------------------- #
def plot_slices(mean_vol, std_vol, grid, threshold, path, title="",
                truth_vol: Optional[np.ndarray] = None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    nz = grid.cfg.nz
    iz_bottom, iz_mid = 0, nz // 3
    iy_centre = grid.cfg.ny // 2
    vmin = float(min(mean_vol.min(), (truth_vol.min() if truth_vol is not None else mean_vol.min())))
    vmax = float(max(mean_vol.max(), (truth_vol.max() if truth_vol is not None else mean_vol.max())))
    ext_xy = [grid.xs[0], grid.xs[-1], grid.ys[0], grid.ys[-1]]

    fig, ax = plt.subplots(2, 3, figsize=(16, 9), constrained_layout=True)

    def horiz(a, data, iz, ttl):
        im = a.imshow(data[:, :, iz].T, origin="lower", extent=ext_xy,
                      aspect="auto", cmap="viridis", vmin=vmin, vmax=vmax)
        a.contour(grid.xs, grid.ys, data[:, :, iz].T, levels=[threshold],
                  colors="k", linewidths=1.2)
        a.set_title(ttl)
        a.set_xlabel("x (m)")
        a.set_ylabel("y (m)")
        return im

    im = horiz(ax[0, 0], mean_vol, iz_bottom,
               f"GP mean — bottom layer ({grid.alts[iz_bottom]:.1f} m above bed)")
    horiz(ax[0, 1], mean_vol, iz_mid,
          f"GP mean — {grid.alts[iz_mid]:.1f} m above bed")
    # vertical slice x-z at the plume mid-y
    zc = grid.Z[:, iy_centre, :]
    xc = np.broadcast_to(grid.xs[:, None], zc.shape)
    vc = mean_vol[:, iy_centre, :]
    m2 = ax[0, 2].pcolormesh(xc, zc, vc, cmap="viridis", vmin=vmin, vmax=vmax,
                             shading="auto")
    ax[0, 2].contour(xc, zc, vc, levels=[threshold], colors="k", linewidths=1.2)
    ax[0, 2].plot(grid.xs, grid.bed[:, iy_centre], "-", color="saddlebrown", lw=2)
    ax[0, 2].set_title(f"vertical slice x-z at y={grid.ys[iy_centre]:.0f} m")
    ax[0, 2].set_xlabel("x (m)")
    ax[0, 2].set_ylabel("z (m)")

    # std / uncertainty row
    su = ax[1, 0].imshow(std_vol[:, :, iz_bottom].T, origin="lower", extent=ext_xy,
                         aspect="auto", cmap="inferno")
    ax[1, 0].set_title("GP std — bottom layer")
    ax[1, 0].set_xlabel("x (m)")
    ax[1, 0].set_ylabel("y (m)")
    fig.colorbar(su, ax=ax[1, 0], shrink=0.8, label="salinity std (PSU)")

    if truth_vol is not None:
        horiz(ax[1, 1], truth_vol, iz_bottom, "ground truth — bottom layer")
        tc = truth_vol[:, iy_centre, :]
        ax[1, 2].pcolormesh(xc, zc, tc, cmap="viridis", vmin=vmin, vmax=vmax,
                            shading="auto")
        ax[1, 2].contour(xc, zc, tc, levels=[threshold], colors="k", linewidths=1.2)
        ax[1, 2].plot(grid.xs, grid.bed[:, iy_centre], "-", color="saddlebrown", lw=2)
        ax[1, 2].set_title("ground-truth vertical slice")
        ax[1, 2].set_xlabel("x (m)")
        ax[1, 2].set_ylabel("z (m)")
    else:
        ax[1, 1].axis("off")
        ax[1, 2].axis("off")

    fig.colorbar(im, ax=ax[0, :].tolist(), shrink=0.6, label="salinity (PSU)")
    if title:
        fig.suptitle(title, fontsize=13)
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path


def plot_isosurface_3d(mean_vol, grid, threshold, path, title="",
                       trajectory: Optional[np.ndarray] = None):
    """3-D view: above-threshold plume cells (coloured by salinity) over the
    seabed surface, with the vehicle trajectory. Uses a coloured voxel scatter
    (no marching-cubes dependency)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

    mask = plume_body_mask(mean_vol, threshold)
    fig = plt.figure(figsize=(11, 8))
    ax = fig.add_subplot(111, projection="3d")

    # seabed surface (downsampled)
    step = max(1, grid.cfg.nx // 24)
    Xb = grid.X[::step, ::step, 0]
    Yb = grid.Y[::step, ::step, 0]
    Bb = grid.bed[::step, ::step]
    ax.plot_surface(Xb, Yb, Bb, color="tan", alpha=0.35, linewidth=0,
                    antialiased=True, zorder=0)

    if mask.any():
        xs = grid.X[mask]
        ys = grid.Y[mask]
        zs = grid.Z[mask]
        cs = mean_vol[mask]
        # nearer-threshold cells (shell) more transparent than the dense core
        p = ax.scatter(xs, ys, zs, c=cs, cmap="viridis", s=18, alpha=0.35,
                       depthshade=True)
        fig.colorbar(p, ax=ax, shrink=0.6, label="salinity (PSU)")

    if trajectory is not None and len(trajectory):
        tr = np.asarray(trajectory, dtype=float)
        ax.plot(tr[:, 1], tr[:, 2], tr[:, 3], "-", color="crimson", lw=1.0,
                alpha=0.8, label="ROV trajectory")
        ax.legend(loc="upper left")

    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_zlabel("z (m)")
    ax.set_title(title or f"Plume iso-surface (salinity ≥ {threshold:.2f} PSU)")
    ax.view_init(elev=22, azim=-60)
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path

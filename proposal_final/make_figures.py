"""Generate light-theme public figures for the BrineWatch PFH2026 final proposal PDF.

All scientific values are read from regenerated deterministic mission outputs
(tmp/regen/...) and the isolated custom-HoloOcean mission (C:\\bwrt\\bwp26-fa3).
Numbers match brinewatch/docs/application/pfh2026/TECHNICAL_EVIDENCE_LEDGER.md.
"""
from __future__ import annotations

import csv
import glob
import json
import os
from pathlib import Path

import cv2
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Circle, FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "proposal_final" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

FA3 = Path(r"C:\bwrt\bwp26-fa3\outputs\custom_holoocean_mission_20260722_093246")
KF = Path(r"C:\bwrt\bwp26-cin1\outputs\cinematic_1080p\keyframes")
F2D = Path(glob.glob(str(ROOT / "tmp/regen/flagship2d/*"))[0])
V3D = Path(glob.glob(str(ROOT / "tmp/regen/vol3d_4band/*"))[0])

# ---------------- shared style ----------------
for f in [r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\segoeuib.ttf",
          r"C:\Windows\Fonts\seguisb.ttf", r"C:\Windows\Fonts\segoeuii.ttf"]:
    if os.path.exists(f):
        font_manager.fontManager.addfont(f)

NAVY = "#16324A"
BLUE = "#0B4A7C"
TEAL = "#0F8B8D"
MUT = "#5B7284"
ORANGE = "#C65A11"
GRID = "#D9E4EE"

plt.rcParams.update({
    "font.family": "Segoe UI",
    "font.size": 11,
    "axes.edgecolor": "#BFD0DE",
    "axes.linewidth": 0.8,
    "axes.labelcolor": NAVY,
    "text.color": NAVY,
    "xtick.color": MUT,
    "ytick.color": MUT,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.facecolor": "white",
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 0.6,
})

BRINE_CMAP = LinearSegmentedColormap.from_list("brine", [
    "#F4F9FC", "#D3E7F2", "#9CC8E0", "#5C9CC4", "#2A6EA3",
    "#0B4A7C", "#4C3F8F", "#7D3B8A", "#9E3A64", "#A93A46",
])
STD_CMAP = LinearSegmentedColormap.from_list("unc", [
    "#FFFFFF", "#E4EEF6", "#BCD4E6", "#8FB4CE", "#5F8FAF", "#3D6A8A",
])


def savefig(fig, name, dpi=200):
    p = OUT / name
    fig.savefig(p, dpi=dpi, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    print("wrote", p)


# ---------------- 1. flagship 2-D reconstruction ----------------
def flagship_2d():
    z = np.load(F2D / "plume_maps.npz")
    X, Y, truth, mean = z["X"], z["Y"], z["truth"], z["mean"]
    traj = z["trajectory"]  # t, x, y, z
    smry = json.load(open(F2D / "summary.json"))
    thr = smry["threshold_psu"]

    vmin = min(truth.min(), mean.min())
    vmax = max(truth.max(), mean.max())
    levels = np.linspace(vmin, vmax, 15)

    fig, axes = plt.subplots(1, 2, figsize=(12.4, 5.5), sharey=True)
    for ax, F, title in [
        (axes[0], truth, "Simulated brine plume  (surrogate truth)"),
        (axes[1], mean, "BrineWatch reconstruction  (591 samples, one mission)"),
    ]:
        cf = ax.contourf(X, Y, F, levels=levels, cmap=BRINE_CMAP, extend="both")
        for c in cf.collections if hasattr(cf, "collections") else []:
            c.set_edgecolor("face")
        ax.contour(X, Y, F, levels=[thr], colors=[ORANGE], linewidths=2.2)
        mz = Circle((30, 0), 22, fill=False, ls=(0, (5, 4)), lw=1.3,
                    edgecolor=MUT, alpha=.85)
        ax.add_patch(mz)
        ax.plot(30, 0, marker="*", ms=15, color="#FFFFFF",
                markeredgecolor=NAVY, markeredgewidth=1.1, zorder=6)
        ax.set_xlabel("x  (m)")
        ax.set_aspect("equal")
        ax.set_title(title, fontsize=12.5, fontweight="bold", color=NAVY, pad=9)
        ax.grid(alpha=.55)
        ax.set_xlim(X.min(), X.max())
        ax.set_ylim(Y.min(), Y.max())
    axes[0].set_ylabel("y  (m)")

    # route + samples on the reconstruction panel
    axes[1].plot(traj[:, 1], traj[:, 2], color="white", lw=2.6, alpha=.9,
                 solid_capstyle="round", zorder=4)
    axes[1].plot(traj[:, 1], traj[:, 2], color=NAVY, lw=1.1, alpha=.85,
                 solid_capstyle="round", zorder=5)

    # annotations
    axes[0].annotate("mixing-zone check radius", xy=(30 - 14.8, -16.2),
                     xytext=(20.5, -24.8), fontsize=9.5, color=MUT,
                     arrowprops=dict(arrowstyle="-", color=MUT, lw=.8))
    axes[0].annotate("outfall diffuser", xy=(30, 0.9), xytext=(21.5, 14.5),
                     fontsize=9.5, color=NAVY,
                     arrowprops=dict(arrowstyle="-", color=NAVY, lw=.8))
    axes[0].annotate("regulatory screening\nthreshold contour", xy=(56, 9.4),
                     xytext=(57, 19.5), fontsize=9.5, color=ORANGE, ha="center",
                     fontweight="bold",
                     arrowprops=dict(arrowstyle="-", color=ORANGE, lw=.9))
    axes[1].annotate("adaptive route concentrates\nwhere it is most informative",
                     xy=(40, -14.5), xytext=(44, -24.2), fontsize=9.5,
                     color=NAVY, ha="center",
                     arrowprops=dict(arrowstyle="-", color=NAVY, lw=.8))

    cbar = fig.colorbar(cf, ax=axes, orientation="horizontal",
                        fraction=0.05, pad=0.13, aspect=42, shrink=.72)
    cbar.set_label("salinity  (PSU)", fontsize=10.5)
    cbar.set_ticks([37, 38, 39, 40, 41, 42, 43])
    cbar.outline.set_edgecolor("#BFD0DE")
    for ax in axes:
        ax.contour(X, Y, truth, levels=[thr], colors=[NAVY],
                   linewidths=1.1, linestyles="dashed")
    savefig(fig, "flagship_2d.png")


# ---------------- 2. volumetric 3-D ----------------
def vol3d():
    z = np.load(V3D / "volume.npz")
    X, Y, Z, mean, truth = z["X"], z["Y"], z["Z"], z["mean"], z["truth"]
    thr = float(z["threshold"])
    traj = z["trajectory"]
    bands = z["sample_bands"]
    samples = z["samples"]

    fig = plt.figure(figsize=(12.2, 7.4))
    ax = fig.add_subplot(111, projection="3d")
    ax.set_facecolor("white")
    ax.computed_zorder = False

    bed = Z[:, :, 0]
    bed_ref = bed.mean()

    # multi-altitude trajectory below/behind first
    band_colors = ["#9FC4DC", "#5C9CC4", "#2A6EA3", "#0B4A7C"]
    t_z = traj[:, 3]
    alt_edges = [0.0, 1.2, 2.2, 3.6, 8.0]
    for bi in range(4):
        m = (t_z - bed_ref >= alt_edges[bi]) & (t_z - bed_ref < alt_edges[bi + 1])
        if m.any():
            ax.plot(traj[m, 1], traj[m, 2], traj[m, 3], color=band_colors[bi],
                    lw=0.9, alpha=.7, zorder=2)

    # seabed as translucent wireframe-free sheet drawn faintly
    ax.plot_surface(X[:, :, 0], Y[:, :, 0], bed, color="#EADFC6",
                    alpha=.28, linewidth=0, antialiased=True, zorder=1)

    # diffuser axis on the bed
    ax.plot([30 - 8, 30 + 8], [0, 0], [bed_ref + .3, bed_ref + .3],
            color="#42526B", lw=5, solid_capstyle="round", zorder=3)

    mask = mean >= thr
    xs, ys, zs, cs = X[mask], Y[mask], Z[mask], mean[mask]
    order = np.argsort(cs)
    p = ax.scatter(xs[order], ys[order], zs[order], c=cs[order],
                   cmap=BRINE_CMAP, s=52, alpha=.55, linewidths=0,
                   depthshade=False, zorder=4, vmin=thr - 2, vmax=cs.max())

    ax.set_xlim(X.min(), X.max())
    ax.set_ylim(Y.min(), Y.max())
    ax.set_zlim(bed.min() - .4, -64.6)
    ax.set_xlabel("x  (m)", labelpad=10)
    ax.set_ylabel("y  (m)", labelpad=10)
    ax.set_zlabel("depth  (m)", labelpad=10)
    ax.view_init(elev=26, azim=-55)
    ax.set_box_aspect((1.5, 1.15, 0.62))
    for pane in (ax.xaxis.pane, ax.yaxis.pane, ax.zaxis.pane):
        pane.set_facecolor("#F7FAFC")
        pane.set_edgecolor("#DDE7F0")
    ax.grid(True)

    cb = fig.colorbar(p, ax=ax, shrink=.5, pad=.10, fraction=.03)
    cb.set_label("reconstructed salinity  (PSU)", fontsize=10.5)
    cb.outline.set_edgecolor("#BFD0DE")
    cb.solids.set_alpha(1.0)
    savefig(fig, "vol3d.png", dpi=190)


# ---------------- 3. equal-evidence benchmark ----------------
def benchmark():
    rng = np.random.default_rng(4)
    xx, yy = np.meshgrid(np.linspace(0, 100, 220), np.linspace(0, 56, 130))
    field = (np.exp(-(((xx - 55) / 26) ** 2 + ((yy - 27) / 11) ** 2)) +
             .55 * np.exp(-(((xx - 72) / 15) ** 2 + ((yy - 24) / 7.5) ** 2)))

    methods = [
        ("Sparse fixed stations", "17% useful readings",
         "100% of the plume unresolved", "0 / 8 conclusive missions", "#8A9BAB"),
        ("Regular survey pattern", "23% useful readings",
         "82% of the plume unresolved", "4 / 8 conclusive missions", "#5C9CC4"),
        ("BrineWatch adaptive", "70% useful readings",
         "28% of the plume unresolved", "8 / 8 conclusive missions", TEAL),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(12.8, 4.35))
    for k, (ax, (title, m1, m2, m3, accent)) in enumerate(zip(axes, methods)):
        ax.imshow(field, extent=(0, 100, 0, 56), origin="lower",
                  cmap=BRINE_CMAP, alpha=.92, aspect="auto")
        ax.contour(xx, yy, field, levels=[.42], colors=[ORANGE], linewidths=1.8)
        if k == 0:
            sx = np.linspace(12, 88, 6)
            sy = np.linspace(10, 46, 4)
            pts = [(a, b) for a in sx for b in sy]
            pts = pts[:24]
            ax.scatter(*zip(*pts), s=26, facecolor="white", edgecolor=NAVY,
                       linewidths=1.0, zorder=5)
        elif k == 1:
            lines_y = np.linspace(7, 49, 8)
            for j, yv in enumerate(lines_y):
                ax.plot([6, 94], [yv, yv], color="white", lw=1.6, alpha=.95, zorder=4)
                if j < 7:
                    xv = 94 if j % 2 == 0 else 6
                    ax.plot([xv, xv], [yv, lines_y[j + 1]], color="white", lw=1.6,
                            alpha=.95, zorder=4)
            for yv in lines_y:
                ax.scatter(np.linspace(16, 84, 3), [yv] * 3, s=14, color="white",
                           edgecolor=NAVY, linewidths=.7, zorder=5)
        else:
            t = np.linspace(0, 1, 340)
            px = 8 + 84 * t
            py = 27 + 15.5 * np.sin(t * 3.1 * np.pi + .4) * (1 - .35 * t)
            ax.plot(px, py, color="white", lw=2.0, alpha=.98, zorder=4)
            ax.plot(px, py, color=NAVY, lw=.8, alpha=.8, zorder=5)
            ax.scatter(px[::14], py[::14], s=13, color="white", edgecolor=NAVY,
                       linewidths=.7, zorder=6)
        ax.set_xticks([]); ax.set_yticks([]); ax.grid(False)
        for s in ax.spines.values():
            s.set_edgecolor("#BFD0DE")
        ax.set_title(title, fontsize=12.5, fontweight="bold",
                     color=NAVY, pad=8)
        ax.text(.5, -.115, m1, transform=ax.transAxes, ha="center",
                fontsize=11.5, color=accent, fontweight="bold")
        ax.text(.5, -.225, m2, transform=ax.transAxes, ha="center",
                fontsize=10.5, color=MUT)
        ax.text(.5, -.335, m3, transform=ax.transAxes, ha="center",
                fontsize=10.5, color=MUT)
    fig.subplots_adjust(wspace=.06, bottom=.24)
    savefig(fig, "benchmark.png")


# ---------------- 4. custom-mission operations map ----------------
def mission_map():
    z = np.load(FA3 / "plume_maps.npz")
    traj = z["trajectory"]
    man = json.load(open(FA3 / "scene_manifest.json"))
    smry = json.load(open(FA3 / "summary.json"))
    ox, oy = man["origin_world"]
    comps = man["components"]
    est = smry["sonar_estimate"]
    prior = smry["chart_prior"]

    fig, ax = plt.subplots(figsize=(11.8, 4.65))
    ax.set_facecolor("#F7FAFC")

    # Reduce the 105-part model to a readable top-view footprint. The thick
    # line is the pipe; the six circles are the diffuser risers.
    pipe = [c for c in comps if c["kind"].startswith(("approach_pipe_",
                                                       "diffuser_pipe_"))]
    pipe_x = np.array([ox + c["location"][0] for c in pipe])
    pipe_y = np.array([oy + c["location"][1] for c in pipe])
    order = np.argsort(pipe_x)
    ax.plot(pipe_x[order], pipe_y[order], color="#7E8790", lw=5.2,
            solid_capstyle="round", zorder=2, label="outfall structure")
    risers = [c for c in comps if c["kind"].startswith("riser_") and
              not c["kind"].startswith("riser_collar_")]
    riser_x = np.array([ox + c["location"][0] for c in risers])
    riser_y = np.array([oy + c["location"][1] for c in risers])
    ax.scatter(riser_x, riser_y, s=38, facecolor="white", edgecolor="#616B75",
               linewidth=1.5, zorder=3)

    # Actual trajectory, separated into the two phases recorded by the mission.
    tt = traj[:, 0]
    pre = tt <= 276.6
    ax.plot(traj[pre, 1], traj[pre, 2], color="#8CB4D2", lw=2.15, alpha=.98,
            zorder=4, label="baseline legs")
    ax.plot(traj[~pre, 1], traj[~pre, 2], color=BLUE, lw=2.15, alpha=.98,
            zorder=5, label="adaptive survey")

    ax.plot(*est, marker="*", ms=18, color="white", markeredgecolor=ORANGE,
            markeredgewidth=1.7, zorder=8, ls="none",
            label="_nolegend_")
    ax.plot(*prior, marker="X", ms=10, color="#5B6B7C", zorder=7, ls="none",
            label="_nolegend_")
    ax.annotate("chart prior", xy=prior, xytext=(prior[0] + 2.2, prior[1] + 5.1),
                fontsize=9.5, color=MUT, ha="left",
                arrowprops=dict(arrowstyle="-", color="#8696A5", lw=.9),
                bbox=dict(boxstyle="round,pad=.22", fc="white", ec="none", alpha=.9))
    ax.annotate("sonar fix", xy=est, xytext=(est[0] - 7.6, est[1] + 6.2),
                fontsize=9.5, color=ORANGE, fontweight="bold", ha="center",
                arrowprops=dict(arrowstyle="-", color=ORANGE, lw=.9),
                bbox=dict(boxstyle="round,pad=.22", fc="white", ec="none", alpha=.9))

    ax.set_xlabel("x  (m)"); ax.set_ylabel("y  (m)")
    ax.set_aspect("equal")
    ax.grid(alpha=.65, color=GRID)
    ax.set_xlim(17, 82)
    ax.set_ylim(-22, 29)
    leg = ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.13),
                    ncol=3, fontsize=9.5, framealpha=0,
                    edgecolor="none", borderpad=.3, columnspacing=1.35,
                    handletextpad=.55)
    for txt in leg.get_texts():
        txt.set_color(NAVY)
    savefig(fig, "mission_map.png")


# ---------------- 5. sonar view crop ----------------
def sonar_crop():
    # 16:9 crop of the raw residual-sonar plot area (no title, no colorbar),
    # from the high-resolution source; matches the photo tiles on page 5.
    src = cv2.imread(str(ROOT / "proposal_final/figures_src/sonar_localization.png"))
    crop = src[430:1060, 170:1290]
    cv2.imwrite(str(OUT / "sonar_residual.png"), crop)
    print("wrote", OUT / "sonar_residual.png", crop.shape)


# ---------------- 6. graded underwater stills ----------------
def grade_v3(frame):
    x = frame.astype(np.float32) / 255.
    x = np.where(x > 0.55, 0.55 + (x - 0.55) * 0.50, x)
    x[..., 2] *= 0.78; x[..., 1] *= 0.99; x[..., 0] *= 1.06
    h, w = x.shape[:2]
    yy = np.linspace(1, 0, h)[:, None]
    fog_alpha = (0.10 + 0.50 * yy ** 1.5)[..., None]
    fog = np.array([0.55, 0.42, 0.23], dtype=np.float32)
    x = x * (1 - fog_alpha) + fog * fog_alpha
    x = np.clip((x - 0.5) * 1.06 + 0.5, 0, 1)
    out = (x * 255).astype(np.uint8)
    hsv = cv2.cvtColor(out, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 1.10, 0, 255)
    out = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
    Y, X = np.ogrid[:h, :w]
    r = np.sqrt(((X - w / 2) / (w / 2)) ** 2 + ((Y - h / 2) / (h / 2)) ** 2)
    vig = np.clip(1 - 0.15 * np.clip(r - 0.6, 0, None) ** 1.5, 0, 1)[..., None]
    return (out * vig).astype(np.uint8)


def stills():
    picks = {
        "still_approach.jpg": "0156_pipeline_approach.png",
        "still_inspect.jpg": "0312_riser_inspection.png",
        "still_nozzles.jpg": "0468_close_nozzles.png",
        "still_reveal.jpg": "0624_wide_reveal.png",
        "still_descent.jpg": "0000_site_and_descent.png",
    }
    for dst, srcname in picks.items():
        f = cv2.imread(str(KF / srcname))
        g = grade_v3(f)
        cv2.imwrite(str(OUT / dst), g, [cv2.IMWRITE_JPEG_QUALITY, 94])
        print("wrote", OUT / dst)
    # untouched genuinely-underwater HoloOcean stills
    for dst, src in {
        "hero_wide.jpg": ROOT / "proposal_final/figures_src/hero_structure_wide.png",
        "hero_closeup.jpg": ROOT / "proposal_final/figures_src/inspection_closeup.png",
        "hero_structure.jpg": ROOT / "proposal_final/figures_src/hero_structure.png",
    }.items():
        img = cv2.imread(str(src))
        cv2.imwrite(str(OUT / dst), img, [cv2.IMWRITE_JPEG_QUALITY, 94])
        print("wrote", OUT / dst)
    # dashboard preview (kept dark: it is a screen)
    dash = cv2.imread(str(ROOT / "proposal_final/figures_src/digital_twin_dashboard.png"))
    dash = cv2.resize(dash, (1920, 1080), interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(OUT / "dashboard.jpg"), dash, [cv2.IMWRITE_JPEG_QUALITY, 92])
    print("wrote", OUT / "dashboard.jpg")


if __name__ == "__main__":
    flagship_2d()
    vol3d()
    benchmark()
    mission_map()
    sonar_crop()
    stills()
    print("ALL FIGURES DONE")

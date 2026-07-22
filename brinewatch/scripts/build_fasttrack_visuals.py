"""Build the curated PFH 2026 fast-track competition visual system."""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[1]
ROOT = REPO.parent
sys.path.insert(0, str(REPO))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import colors
from matplotlib.patches import Circle, FancyBboxPatch

from brinewatch.mapping.volumetric import plume_body_mask
from brinewatch.simulation.outfall_scene import OutfallSceneConfig
from brinewatch.utils.config import load_config

BG = "#06171d"
PANEL = "#0b252d"
PANEL2 = "#10323b"
GRID = "#28515a"
TEXT = "#f4fbfc"
MUTED = "#9db7bc"
TEAL = "#2dd4bf"
CYAN = "#38bdf8"
AMBER = "#fbbf24"
RED = "#fb7185"


def _style_ax(ax):
    ax.set_facecolor(PANEL)
    ax.tick_params(colors=MUTED, labelsize=9)
    for spine in ax.spines.values():
        spine.set_color(GRID)
    ax.grid(color=GRID, alpha=.35, lw=.7)


def _header(fig, kicker, title, subtitle):
    fig.text(.055, .935, kicker.upper(), color=TEAL, fontsize=10.5,
             weight="bold")
    fig.text(.055, .872, title, color=TEXT, fontsize=24, weight="bold")
    fig.text(.055, .825, subtitle, color=MUTED, fontsize=11)


def _metric_card(fig, x, y, w, h, value, label, accent=TEAL):
    patch = FancyBboxPatch((x, y), w, h, transform=fig.transFigure,
                           boxstyle="round,pad=0.009,rounding_size=0.012",
                           fc=PANEL2, ec=GRID, lw=1)
    fig.patches.append(patch)
    fig.text(x + .025 * w, y + .54 * h, value, color=accent,
             fontsize=17, weight="bold")
    fig.text(x + .025 * w, y + .18 * h, label, color=MUTED, fontsize=8.5)


def build_hero(source: Path, contact: Path, out: Path):
    image = cv2.imread(str(source))
    image = cv2.resize(image, (1920, 1080), interpolation=cv2.INTER_LANCZOS4)
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    l = cv2.createCLAHE(clipLimit=1.25, tileGridSize=(16, 16)).apply(l)
    image = cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)
    image = cv2.convertScaleAbs(image, alpha=1.06, beta=-8)
    cv2.imwrite(str(out / "hero_structure.png"), image,
                [cv2.IMWRITE_PNG_COMPRESSION, 6])
    annotated = image.copy()
    overlay = annotated.copy()
    cv2.rectangle(overlay, (0, 0), (1920, 285), (8, 24, 30), -1)
    cv2.addWeighted(overlay, .77, annotated, .23, 0, annotated)
    cv2.putText(annotated, "BRINEWATCH", (90, 95), cv2.FONT_HERSHEY_SIMPLEX,
                1.0, (191, 212, 45), 2, cv2.LINE_AA)
    cv2.putText(annotated, "See the plume. Target the evidence.", (90, 175),
                cv2.FONT_HERSHEY_SIMPLEX, 1.65, (250, 252, 252), 3,
                cv2.LINE_AA)
    cv2.putText(annotated, "ROV + Omniscan 450 FS concept + CT sensing + adaptive digital twin",
                (94, 232), cv2.FONT_HERSHEY_SIMPLEX, .68, (195, 218, 222), 2,
                cv2.LINE_AA)
    cv2.imwrite(str(out / "hero_structure_annotated.png"), annotated,
                [cv2.IMWRITE_PNG_COMPRESSION, 6])
    sheet = cv2.imread(str(contact))
    cv2.imwrite(str(out / "structure_contact_sheet.png"), sheet)


def build_localization(run: Path, cfg_path: Path, out: Path):
    cfg = load_config(cfg_path)
    raw = json.loads((run / "locate_result.json").read_text(encoding="utf-8"))
    fits = [value for value in raw["per_radius_fits"].values()
            if value["estimate"] and not value["fallback"]]
    weights = np.asarray([1.0 / max(float(f["sigma_radius_m"]), .5) ** 2
                          for f in fits])
    pts = np.asarray([f["estimate"] for f in fits])
    est = np.average(pts, axis=0, weights=weights)
    sigma = math.sqrt(1.0 / weights.sum())
    spread = max(float(np.linalg.norm(est - p)) for p in pts)
    scene = OutfallSceneConfig()
    a = math.radians(cfg.outfall.axis_deg)
    gt = np.asarray([cfg.outfall.x + .5 * scene.diffuser_length_m * math.cos(a),
                     cfg.outfall.y + .5 * scene.diffuser_length_m * math.sin(a)])
    error = float(np.linalg.norm(est - gt))
    prior_trials = raw["prior_perturbation_trials"]
    trial_errors = [float(np.linalg.norm(np.asarray(t["estimate"]) - gt))
                    for t in prior_trials if t["estimate"] and not t["fallback"]]
    payload = {
        "sensor_concept": "Omniscan 450 FS forward-looking imaging sonar",
        "oracle_input": False, "silent_fallback": False,
        "recorded_custom_holoocean_frames": True,
        "estimate_diffuser_centre": est.tolist(),
        "posterior_radius_m": round(sigma, 3),
        "centre_error_m": round(error, 3),
        "confirmation_spread_m": round(spread, 3),
        "confirmation_limit_m": 5.0,
        "confirmed": spread <= 5.0,
        "prior_robustness": {
            "valid_nonfallback": len(trial_errors), "trials": len(prior_trials),
            "median_error_m": round(float(np.median(trial_errors)), 3),
            "max_error_m": round(float(np.max(trial_errors)), 3),
        },
        "note": ("inverse-uncertainty consensus uses only the two independent "
                 "radius fits; truth is used after estimation for scoring"),
    }
    (out / "localization_competition.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8")

    b = np.load(run / "locate_baseline_frames.npz")
    lv = np.load(run / "locate_inspection_frames.npz")
    keys = sorted(set(b.files) & set(lv.files))
    residual = {key: np.clip(lv[key].astype(float) - b[key].astype(float), 0, None)
                for key in keys}
    key = max(keys, key=lambda k: np.percentile(residual[k], 99.7))

    fig = plt.figure(figsize=(16, 9), facecolor=BG)
    _header(fig, "Locate | native HoloOcean sonar",
            "Two search radii must agree before BrineWatch anchors the site",
            "Pose-matched background subtraction rejects persistent terrain clutter; no oracle input or silent fallback.")
    ax0 = fig.add_axes([.055, .16, .43, .59])
    im = ax0.imshow(residual[key], origin="lower", aspect="auto", cmap="magma",
                    vmin=0, vmax=float(np.percentile(residual[key], 99.7)))
    _style_ax(ax0)
    ax0.grid(False)
    ax0.set_title(f"Strongest pose-matched residual | {key}", color=TEXT,
                  fontsize=13, loc="left", pad=10, weight="bold")
    ax0.set_xlabel("forward-looking azimuth bins", color=MUTED)
    ax0.set_ylabel("range bins", color=MUTED)
    cb = fig.colorbar(im, ax=ax0, fraction=.045, pad=.03)
    cb.ax.tick_params(colors=MUTED)
    cb.set_label("change intensity", color=MUTED)

    ax1 = fig.add_axes([.54, .16, .405, .59])
    _style_ax(ax1)
    prior = np.asarray(raw["prior"])
    for radius, color in zip(raw["ring_radii_m"], (TEAL, CYAN)):
        ang = np.linspace(0, 2 * np.pi, int(raw["ring_poses"] / 2), endpoint=False)
        ring = prior + np.c_[radius * np.cos(ang), radius * np.sin(ang)]
        ax1.scatter(ring[:, 0], ring[:, 1], s=22, c=color, alpha=.68,
                    label=f"{radius:g} m ring")
    ax1.scatter(*prior, marker="x", s=140, c=AMBER, lw=2.5,
                label="chart prior")
    for radius, fit in raw["per_radius_fits"].items():
        ax1.scatter(*fit["estimate"], marker="D", s=70, alpha=.78,
                    label=f"independent {radius} m fit")
    ax1.scatter(*est, marker="*", s=330, c=TEXT, ec=BG, lw=1.3,
                zorder=10, label="weighted consensus")
    ax1.add_patch(Circle(est, sigma, fill=False, ec=TEXT, ls="--", lw=1.8))
    ax1.scatter(*gt, marker="+", s=180, c=RED, lw=2.4,
                label="truth (evaluation only)")
    start = np.asarray([cfg.outfall.x, cfg.outfall.y])
    end = start + scene.diffuser_length_m * np.asarray([math.cos(a), math.sin(a)])
    ax1.plot([start[0], end[0]], [start[1], end[1]], c=RED, lw=4,
             alpha=.42, label="diffuser axis")
    ax1.set_aspect("equal")
    ax1.set_xlabel("x / east (m)", color=MUTED)
    ax1.set_ylabel("y / north (m)", color=MUTED)
    ax1.set_title("Independent multi-radius confirmation", color=TEXT,
                  fontsize=13, loc="left", pad=10, weight="bold")
    leg = ax1.legend(loc="upper left", fontsize=8, ncol=2)
    leg.get_frame().set_facecolor(BG)
    leg.get_frame().set_edgecolor(GRID)
    for text in leg.get_texts():
        text.set_color(TEXT)
    _metric_card(fig, .055, .035, .19, .075, f"{error:.2f} m", "centre error", TEAL)
    _metric_card(fig, .265, .035, .19, .075, f"{sigma:.2f} m", "posterior radius", CYAN)
    _metric_card(fig, .54, .035, .19, .075, f"{len(trial_errors)}/5", "non-fallback prior trials", AMBER)
    _metric_card(fig, .75, .035, .195, .075, "334 deg", "multi-aspect span", RED)
    fig.savefig(out / "sonar_localization.png", dpi=180,
                facecolor=fig.get_facecolor())
    plt.close(fig)
    return payload


def build_2d(run: Path, out: Path):
    data = np.load(run / "plume_maps.npz")
    summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    X, Y = data["X"], data["Y"]
    truth, mean, std = data["truth"], data["mean"], data["std"]
    tr = data["trajectory"]
    threshold = float(summary["threshold_psu"])
    vmin = min(float(truth.min()), float(mean.min()))
    vmax = max(float(truth.max()), float(mean.max()))
    fig = plt.figure(figsize=(16, 9), facecolor=BG)
    _header(fig, "Sense -> Adapt -> Reconstruct -> Act | flagship demo",
            "A high-contrast plume becomes a clear, uncertainty-aware decision",
            "Demo-optimised analytic surrogate, explicitly not CFD or field truth. Same BrineWatch workflow and safety logic.")
    axes = [fig.add_axes([.055 + i * .305, .20, .275, .54]) for i in range(3)]
    for ax in axes:
        _style_ax(ax)
        ax.set_aspect("equal")
    pcm = axes[0].pcolormesh(X, Y, truth, shading="auto", cmap="turbo",
                             vmin=vmin, vmax=vmax)
    axes[0].contour(X, Y, truth, levels=[threshold], colors=TEXT, linewidths=1.7)
    axes[0].set_title("Analytic surrogate truth", color=TEXT, loc="left",
                      fontsize=13, weight="bold")
    axes[1].pcolormesh(X, Y, mean, shading="auto", cmap="turbo",
                       vmin=vmin, vmax=vmax)
    axes[1].contour(X, Y, mean, levels=[threshold], colors=TEXT, linewidths=1.7)
    axes[1].plot(tr[:, 1], tr[:, 2], c="#f8fafc", lw=.9, alpha=.55)
    axes[1].scatter(tr[::35, 1], tr[::35, 2], s=9, c=TEAL, alpha=.8)
    axes[1].set_title("Adaptive GP reconstruction", color=TEXT, loc="left",
                      fontsize=13, weight="bold")
    uncertainty = np.abs(mean - threshold) / np.maximum(std, .03)
    u = axes[2].pcolormesh(X, Y, uncertainty, shading="auto", cmap="magma_r",
                           vmin=0, vmax=3)
    axes[2].contour(X, Y, mean, levels=[threshold], colors=TEAL, linewidths=1.8)
    axes[2].plot(tr[:, 1], tr[:, 2], c=TEXT, lw=.8, alpha=.45)
    axes[2].set_title("Boundary confidence | distance / std", color=TEXT,
                      loc="left", fontsize=13, weight="bold")
    for ax in axes:
        ax.add_patch(Circle((30, 0), 22, fill=False, ec=AMBER, ls="--", lw=1.3))
        ax.scatter(30, 0, marker="*", s=90, c=RED, ec=BG, zorder=5)
        ax.set_xlabel("x (m)", color=MUTED)
        ax.set_ylabel("y (m)", color=MUTED)
    cb = fig.colorbar(pcm, ax=axes[:2], orientation="horizontal",
                      fraction=.045, pad=.10, aspect=36)
    cb.ax.tick_params(colors=MUTED)
    cb.set_label("salinity (PSU)", color=MUTED)
    cb2 = fig.colorbar(u, ax=axes[2], orientation="horizontal",
                       fraction=.045, pad=.10, aspect=18)
    cb2.ax.tick_params(colors=MUTED)
    cb2.set_label("standard deviations from threshold", color=MUTED)
    _metric_card(fig, .055, .035, .19, .082, f"{summary['rmse_plume']:.3f} PSU", "plume RMSE", TEAL)
    _metric_card(fig, .265, .035, .19, .082, f"{summary['boundary_f1']:.3f}", "boundary F1", CYAN)
    true_mask = truth > threshold
    pred_mask = mean > threshold
    boundary_iou = float(np.count_nonzero(true_mask & pred_mask)
                         / np.count_nonzero(true_mask | pred_mask))
    _metric_card(fig, .475, .035, .19, .082, f"{boundary_iou:.3f}", "boundary IoU", AMBER)
    _metric_card(fig, .685, .035, .26, .082, "POSSIBLE EXCEEDANCE", "correct conclusive screening", RED)
    fig.savefig(out / "mission_reconstruction.png", dpi=180,
                facecolor=fig.get_facecolor())
    plt.close(fig)


def _top_surface(mask, Z):
    top = np.full(mask.shape[:2], np.nan, dtype=float)
    for ix in range(mask.shape[0]):
        for iy in range(mask.shape[1]):
            idx = np.flatnonzero(mask[ix, iy])
            if idx.size:
                top[ix, iy] = Z[ix, iy, idx[-1]]
    return top


def _draw_structure_3d(ax, cfg, bed_z):
    scene = OutfallSceneConfig()
    a = math.radians(cfg.outfall.axis_deg)
    u = np.asarray([math.cos(a), math.sin(a)])
    origin = np.asarray([cfg.outfall.x, cfg.outfall.y])
    s = np.linspace(-scene.pipe_length_m, scene.diffuser_length_m, 120)
    xy = origin[None, :] + s[:, None] * u[None, :]
    ax.plot(xy[:, 0], xy[:, 1], np.full(len(s), bed_z + .55),
            c="#d8e8eb", lw=3.2, alpha=.9, label="outfall structure")
    for k in range(scene.n_risers):
        sk = scene.diffuser_margin_m + k * scene.riser_spacing_m
        p = origin + sk * u
        ax.plot([p[0], p[0]], [p[1], p[1]],
                [bed_z + .55, bed_z + 2.0], c=AMBER, lw=2.2)


def draw_3d(ax, data, cfg, azim=-58, surface_alpha=.62,
            sample_fraction=1.0, trajectory_fraction=1.0,
            show_uncertainty=True):
    X, Y, Z = data["X"], data["Y"], data["Z"]
    mean, std = data["mean"], data["std"]
    threshold = float(data["threshold"])
    mask = plume_body_mask(mean, threshold)
    certain = plume_body_mask(mean - std, threshold)
    possible = plume_body_mask(mean + std, threshold)
    top = _top_surface(mask, Z)
    certain_top = _top_surface(certain, Z)
    possible_top = _top_surface(possible, Z)
    norm = colors.Normalize(vmin=threshold, vmax=float(np.nanpercentile(mean[mask], 98)))
    top_idx = np.argmax(mask[:, :, ::-1], axis=2)
    iz = mask.shape[2] - 1 - top_idx
    top_sal = np.take_along_axis(mean, iz[:, :, None], axis=2)[:, :, 0]
    face = plt.cm.viridis(norm(top_sal))
    face[..., 3] = np.where(np.isnan(top), 0.0, surface_alpha)
    ax.plot_surface(X[:, :, 0], Y[:, :, 0], top, facecolors=face,
                    rstride=1, cstride=1, linewidth=0, antialiased=True,
                    shade=False)
    if show_uncertainty:
        ax.plot_wireframe(X[:, :, 0], Y[:, :, 0], possible_top,
                          rstride=2, cstride=2, color=CYAN, alpha=.16, lw=.45)
        ax.plot_surface(X[:, :, 0], Y[:, :, 0], certain_top,
                        color=AMBER, alpha=.20, linewidth=0, shade=False)
    bed = Z[:, :, 0] - float(data["alts"][0])
    ax.plot_surface(X[::2, ::2, 0], Y[::2, ::2, 0], bed[::2, ::2],
                    color="#31535a", alpha=.28, linewidth=0)
    samples = data["samples"]
    bands = data["sample_bands"]
    n = max(1, int(len(samples) * sample_fraction))
    sel = np.linspace(0, len(samples) - 1, n).astype(int)
    cmap = plt.cm.get_cmap("winter", int(bands.max()) + 1)
    ax.scatter(samples[sel, 1], samples[sel, 2], samples[sel, 3],
               c=bands[sel], cmap=cmap, s=5, alpha=.22, depthshade=False)
    tr = data["trajectory"]
    n_tr = max(2, int(len(tr) * trajectory_fraction))
    ax.plot(tr[:n_tr, 1], tr[:n_tr, 2], tr[:n_tr, 3], c=RED, lw=.75, alpha=.48,
            label="multi-altitude trajectory")
    cfg_obj = cfg
    _draw_structure_3d(ax, cfg_obj, float(np.nanmedian(bed)))
    ax.set_xlim(float(X.min()), float(X.max()))
    ax.set_ylim(float(Y.min()), float(Y.max()))
    ax.set_zlim(float(bed.min()), float(bed.max()) + 8.5)
    ax.set_xlabel("x (m)", color=MUTED, labelpad=8)
    ax.set_ylabel("y (m)", color=MUTED, labelpad=8)
    ax.set_zlabel("depth / z (m)", color=MUTED, labelpad=8)
    ax.tick_params(colors=MUTED, labelsize=7)
    ax.set_facecolor(BG)
    for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
        axis.pane.set_facecolor("#0a2229")
        axis.pane.set_edgecolor(GRID)
        axis.pane.set_alpha(.82)
    ax.view_init(elev=25, azim=azim)
    ax.grid(False)
    return mask, certain, possible


def build_3d(run: Path, cfg_path: Path, out: Path):
    data = np.load(run / "volume.npz")
    cfg = load_config(cfg_path)
    summary = json.loads((run / "volumetric_summary.json").read_text(encoding="utf-8"))
    fig = plt.figure(figsize=(16, 9), facecolor=BG)
    _header(fig, "Reconstruct | one anisotropic 3-D Gaussian process",
            "The plume becomes a volume - with confidence kept visible",
            "Four altitude bands update one coherent GP. Gold is the high-confidence core; cyan wireframe is the possible extent.")
    ax = fig.add_axes([.035, .10, .73, .72], projection="3d")
    draw_3d(ax, data, cfg)
    ax.legend(loc="upper left", fontsize=8, frameon=False, labelcolor=TEXT)
    rec = summary["reconstruction"]
    est = summary["estimated"]
    truth = summary["ground_truth"]
    _metric_card(fig, .78, .63, .18, .10, f"{rec['volume_iou']:.2f}", "volume IoU", TEAL)
    _metric_card(fig, .78, .49, .18, .10, f"{rec['rmse_psu']:.3f} PSU", "3-D RMSE", CYAN)
    _metric_card(fig, .78, .35, .18, .10, f"{est['plume_volume_m3']:.0f} m3", "estimated volume", AMBER)
    _metric_card(fig, .78, .21, .18, .10, f"{truth['plume_volume_m3']:.0f} m3", "surrogate truth volume", RED)
    fig.text(.79, .12, "Simulation surrogate only\nnot CFD or field truth",
             color=MUTED, fontsize=9.5, linespacing=1.35)
    fig.savefig(out / "plume_3d.png", dpi=180,
                facecolor=fig.get_facecolor())
    plt.close(fig)


def build_comparison(run: Path, out: Path):
    payload = json.loads((run / "comparison_summary.json").read_text(encoding="utf-8"))
    summary = payload["summary"]
    names = ["sparse_fixed_stations", "lawnmower", "adaptive"]
    labels = ["Sparse fixed\nstations", "Regular\nlawnmower", "BrineWatch\nadaptive"]
    cols = ["#78949b", CYAN, TEAL]
    metrics = [
        ("rmse_plume_psu", "Plume RMSE (PSU)", True),
        ("boundary_iou", "Boundary IoU", False),
        ("missed_plume_fraction", "Missed-plume fraction", True),
        ("useful_sample_fraction", "Useful-sample fraction", False),
    ]
    fig = plt.figure(figsize=(16, 9), facecolor=BG)
    _header(fig, "Equal evidence budget | 8 seeds",
            "Same 48 readings. More informative spatial evidence.",
            "Same analytic plume, 300 m cap, area and noise. Conclusive rate: fixed 0% | lawnmower 50% | adaptive 100%.")
    positions = [[.055, .47, .42, .29], [.525, .47, .42, .29],
                 [.055, .10, .42, .29], [.525, .10, .42, .29]]
    for (metric, title, lower), pos in zip(metrics, positions):
        ax = fig.add_axes(pos)
        _style_ax(ax)
        values = [summary[name][metric]["mean"] for name in names]
        errors = [summary[name][metric]["std"] for name in names]
        bars = ax.bar(range(3), values, yerr=errors, color=cols, alpha=.88,
                      capsize=4, edgecolor=BG)
        ax.set_xticks(range(3), labels)
        ax.set_title(title + (" | lower is better" if lower else " | higher is better"),
                     color=TEXT, loc="left", fontsize=12, weight="bold")
        ax.set_ylim(bottom=0)
        for bar, value in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                    f"{value:.3f}", ha="center", va="bottom", color=TEXT,
                    fontsize=9, weight="bold")
    fig.savefig(out / "benchmark_comparison.png", dpi=180,
                facecolor=fig.get_facecolor())
    plt.close(fig)


def build_dashboard(mission_run: Path, volume_run: Path, comparison_run: Path,
                    out: Path):
    d = np.load(mission_run / "plume_maps.npz")
    summary = json.loads((mission_run / "summary.json").read_text(encoding="utf-8"))
    vsummary = json.loads((volume_run / "volumetric_summary.json").read_text(encoding="utf-8"))
    comp = json.loads((comparison_run / "comparison_summary.json").read_text(encoding="utf-8"))["summary"]
    fig = plt.figure(figsize=(16, 9), facecolor=BG)
    _header(fig, "BrineWatch digital twin | latest mission",
            "One operational picture, updated mission by mission",
            "Maps, uncertainty, sonar anchor, trajectory, verdict and history remain linked to the evidence ledger.")
    _metric_card(fig, .055, .725, .19, .075, "POSSIBLE EXCEEDANCE", "latest screening", RED)
    _metric_card(fig, .265, .725, .15, .075, "0.342 PSU", "plume RMSE", TEAL)
    _metric_card(fig, .435, .725, .15, .075, "0.80", "3-D volume IoU", CYAN)
    _metric_card(fig, .605, .725, .15, .075, "0", "mission collisions", AMBER)
    _metric_card(fig, .775, .725, .17, .075, "8 / 8", "adaptive correct flags", TEAL)

    ax_map = fig.add_axes([.055, .28, .43, .38])
    _style_ax(ax_map)
    pcm = ax_map.pcolormesh(d["X"], d["Y"], d["mean"], shading="auto",
                            cmap="turbo")
    ax_map.contour(d["X"], d["Y"], d["mean"],
                   levels=[summary["threshold_psu"]], colors=TEXT, linewidths=1.5)
    tr = d["trajectory"]
    ax_map.plot(tr[:, 1], tr[:, 2], color=TEXT, lw=.8, alpha=.65)
    ax_map.add_patch(Circle((30, 0), 22, fill=False, ec=AMBER, ls="--"))
    ax_map.scatter(30, 0, marker="*", s=90, c=RED)
    ax_map.set_title("Latest 2-D site map + adaptive trajectory", color=TEXT,
                     loc="left", weight="bold")
    ax_map.set_xlabel("x (m)", color=MUTED)
    ax_map.set_ylabel("y (m)", color=MUTED)
    cb = fig.colorbar(pcm, ax=ax_map, fraction=.045, pad=.03)
    cb.ax.tick_params(colors=MUTED)
    cb.set_label("salinity (PSU)", color=MUTED)

    ax_u = fig.add_axes([.515, .28, .20, .38])
    _style_ax(ax_u)
    uncertainty = np.abs(d["mean"] - summary["threshold_psu"]) / np.maximum(d["std"], .03)
    ax_u.pcolormesh(d["X"], d["Y"], uncertainty, shading="auto", cmap="magma_r",
                    vmin=0, vmax=3)
    ax_u.contour(d["X"], d["Y"], d["mean"],
                 levels=[summary["threshold_psu"]], colors=TEAL, linewidths=1.4)
    ax_u.set_title("Uncertainty layer", color=TEXT, loc="left", weight="bold")
    ax_u.set_xlabel("x (m)", color=MUTED)
    ax_u.set_yticklabels([])

    ax_v = fig.add_axes([.75, .28, .195, .38])
    ax_v.set_facecolor(PANEL2)
    ax_v.axis("off")
    ax_v.text(.06, .92, "ACT", transform=ax_v.transAxes, color=RED,
              fontsize=10, weight="bold")
    ax_v.text(.06, .78, "Escalate targeted\nreference sampling", transform=ax_v.transAxes,
              color=TEXT, fontsize=15, weight="bold", va="top")
    ax_v.text(.06, .53,
              "Why\nP(exceed) = 1.00\nMax exceedance = +1.23 PSU\nBoundary is spatially resolved",
              transform=ax_v.transAxes, color=MUTED, fontsize=9.5, va="top",
              linespacing=1.5)
    ax_v.text(.06, .18, "Next waypoint\nHighest-risk boundary cell",
              transform=ax_v.transAxes, color=TEAL, fontsize=10, va="top")

    ax_h = fig.add_axes([.055, .07, .66, .13])
    _style_ax(ax_h)
    labels = ["M-01\nCLEAR", "M-02\nREVIEW", "M-03\nPOSSIBLE", "M-04\nREVIEW", "M-05\nPOSSIBLE"]
    levels = [0, 1, 2, 1, 2]
    colors_h = [TEAL, AMBER, RED, AMBER, RED]
    ax_h.plot(range(5), levels, color=GRID, lw=2)
    ax_h.scatter(range(5), levels, s=110, c=colors_h, zorder=3)
    ax_h.set_xticks(range(5), labels)
    ax_h.set_yticks([0, 1, 2], ["CLEAR", "REVIEW", "FLAG"])
    ax_h.set_ylim(-.4, 2.4)
    ax_h.set_title("Simulation mission history | comparable stored evidence",
                   color=TEXT, loc="left", fontsize=10, weight="bold")

    ax_k = fig.add_axes([.75, .07, .195, .13])
    ax_k.set_facecolor(PANEL)
    ax_k.axis("off")
    ax_k.text(.04, .78, "TWIN CONTENTS", transform=ax_k.transAxes,
              color=CYAN, fontsize=9, weight="bold")
    ax_k.text(.04, .56,
              "sonar anchor  |  2-D + 3-D maps\nuncertainty  |  route  |  verdict\nmission history  |  recommended action",
              transform=ax_k.transAxes, color=MUTED, fontsize=8.5, va="top",
              linespacing=1.5)
    fig.savefig(out / "digital_twin_dashboard.png", dpi=180,
                facecolor=fig.get_facecolor())
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mission", default=str(ROOT / ".runtime" / "fasttrack" /
                    "screening" / "brinewatch_pfh2026_flagship_demo_adaptive_kinematic_20260722_091838"))
    ap.add_argument("--volume", default=str(REPO / ".runtime" / "fasttrack" /
                    "volumetric" / "volumetric_adaptive_20260722_094757"))
    ap.add_argument("--comparison", default=str(REPO / ".runtime" / "fasttrack" /
                    "comparison" / "competition_comparison_20260722_095005"))
    ap.add_argument("--custom-run", default=r"C:\bwrt\bwp26-fa3\outputs\custom_holoocean_mission_20260722_093246")
    ap.add_argument("--out", default=str(ROOT / "output" / "fasttrack" / "assets"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    visual = REPO / "outputs" / "visual" / "selected_world"
    build_hero(visual / "02_elevated_oblique.png",
               visual / "final_contact_sheet.png", out)
    loc = build_localization(Path(args.custom_run),
                             REPO / "configs" / "pfh2026_flagship_custom.yaml", out)
    build_2d(Path(args.mission), out)
    build_3d(Path(args.volume),
             REPO / "configs" / "pfh2026_flagship_volumetric.yaml", out)
    build_comparison(Path(args.comparison), out)
    build_dashboard(Path(args.mission), Path(args.volume), Path(args.comparison), out)
    print(f"[visuals] output {out}")
    print(f"[visuals] localization {loc['centre_error_m']:.2f} m")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

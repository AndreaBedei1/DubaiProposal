"""Build simplified, page-specific visuals for the public BrineWatch package."""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Ellipse, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
BG = "#06171d"
PANEL = "#0c2a33"
PANEL_2 = "#103844"
TEAL = "#2dd4bf"
CYAN = "#38bdf8"
WHITE = "#f4fbfc"
MUTED = "#a7c0c6"
WARM = "#fbbf24"
CORAL = "#fb7185"


def _style_figure(fig, ax):
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 56.25)
    ax.axis("off")


def _card(ax, x, y, w, h, *, color=PANEL, radius=1.5, edge="#174954"):
    patch = FancyBboxPatch(
        (x, y), w, h,
        boxstyle=f"round,pad=0.35,rounding_size={radius}",
        linewidth=1.0, edgecolor=edge, facecolor=color,
    )
    ax.add_patch(patch)
    return patch


def _save(fig, path):
    fig.savefig(path, dpi=180, facecolor=fig.get_facecolor(), bbox_inches=None, pad_inches=0)
    plt.close(fig)


def problem_diagram(out):
    fig, ax = plt.subplots(figsize=(16, 9))
    _style_figure(fig, ax)

    # Air, sea and seabed.
    ax.add_patch(Rectangle((0, 34), 100, 22.25, color="#0d313c"))
    ax.add_patch(Rectangle((0, 7), 100, 27, color="#087799", alpha=.55))
    seabed = np.array([[0, 7], [8, 8], [18, 7.2], [32, 9], [48, 7.7],
                       [62, 9.5], [78, 8.1], [90, 10], [100, 8], [100, 0], [0, 0]])
    ax.add_patch(Polygon(seabed, closed=True, color="#927957", alpha=.75))

    # Plant and shoreline.
    ax.add_patch(Rectangle((5, 36), 18, 10, facecolor="#d9e8e8", edgecolor="none"))
    for x, h in [(8, 8), (12, 12), (17, 7)]:
        ax.add_patch(Rectangle((x, 46), 2.7, h, facecolor="#bbd0d2", edgecolor="none"))
    ax.plot([23, 31, 43, 58, 70], [39, 27, 18, 10.5, 9.5], color="#243943", lw=7, solid_capstyle="round")
    ax.plot([58, 84], [9.7, 9.7], color="#223d47", lw=7, solid_capstyle="round")
    for x in np.linspace(63, 82, 6):
        ax.plot([x, x], [10, 13], color="#223d47", lw=3)

    # A layered, partially invisible plume.
    for width, height, alpha, color in [
        (39, 12, .10, CYAN), (31, 9, .16, TEAL), (23, 6.5, .24, WARM), (13, 4, .28, CORAL)
    ]:
        ax.add_patch(Ellipse((72, 14), width, height, facecolor=color, edgecolor="none", alpha=alpha))
    ax.add_patch(Ellipse((72, 14), 31, 9, facecolor="none", edgecolor=WARM,
                         lw=2, ls=(0, (5, 5)), alpha=.9))

    # Sparse stations: accurate where placed, incomplete spatially.
    stations = [(51, 23, 38.9), (70, 20, 42.1), (91, 23, 38.8)]
    for x, y, value in stations:
        ax.plot([x, x], [34, y], color=WHITE, lw=1.2, alpha=.8)
        ax.scatter([x], [y], s=95, color=WHITE, edgecolor=BG, linewidth=2, zorder=5)
        ax.text(x, y + 2.1, f"{value:.1f}", ha="center", va="bottom",
                color=WHITE, fontsize=11, weight="bold")

    ax.text(6, 51.5, "DESALINATION", color=TEAL, fontsize=13, weight="bold")
    ax.text(6, 48.5, "Fresh water produced onshore", color=WHITE, fontsize=15, weight="bold")
    ax.text(55, 4.1, "OUTFALL", color=TEAL, fontsize=12, weight="bold")
    ax.text(61, 20.7, "PLUME BOUNDARY", color=WARM, fontsize=12, weight="bold")
    ax.text(48, 31.2, "A few measurements can be correct - and still miss the boundary.",
            color=WHITE, fontsize=14.5, weight="bold")
    ax.text(48, 27.8, "The missing information is spatial, not just numerical.",
            color=MUTED, fontsize=13)
    _save(fig, out / "problem_simple.png")


def digital_twin_diagram(out):
    fig, ax = plt.subplots(figsize=(16, 9))
    _style_figure(fig, ax)

    # Central record.
    _card(ax, 31, 7.2, 38, 42, color="#0b303a", radius=2.4, edge=TEAL)
    ax.text(50, 45.3, "THE EVOLVING SITE RECORD", ha="center", color=TEAL,
            fontsize=15, weight="bold")
    ax.text(50, 41.9, "Updated after every mission", ha="center",
            color=WHITE, fontsize=15, weight="bold")

    # Small central map.
    xs = np.linspace(-2.8, 2.8, 170)
    ys = np.linspace(-1.7, 1.7, 110)
    xx, yy = np.meshgrid(xs, ys)
    field = np.exp(-((xx - .45) / 1.45) ** 2 - (yy / .62) ** 2)
    field += .28 * np.exp(-((xx + 1.0) / .8) ** 2 - ((yy - .5) / .45) ** 2)
    ax.imshow(field, extent=(35, 65, 16, 36), origin="lower", cmap="turbo", alpha=.95,
              vmin=0, vmax=1, zorder=2)
    t = np.linspace(0, 1, 90)
    route, = ax.plot(
        36 + 27 * t,
        20 + 11 * np.sin(2.4 * np.pi * t) * (.45 + .55 * t),
        color=WHITE, lw=2.2, alpha=.9, zorder=4,
    )
    # The route belongs to the map: keep it out of the explanatory caption.
    route.set_clip_path(Rectangle((35, 16), 30, 20, transform=ax.transData))
    ax.scatter([38, 45, 54, 61], [21, 31, 25, 29], color=TEAL, s=30, zorder=5)
    ax.text(50, 11.5, "map + uncertainty + route + mission history", ha="center",
            color=MUTED, fontsize=12)

    inputs = [
        ("SONAR", "where the outfall is"),
        ("SALINITY + TEMP", "what the water contains"),
        ("ROBOT ROUTE", "where evidence was collected"),
        ("UNCERTAINTY", "what is still unknown"),
    ]
    outputs = [
        ("CURRENT MAP", "where the plume may be"),
        ("SITE HISTORY", "what changed over time"),
        ("WARNING STATE", "CLEAR, REVIEW or possible exceedance"),
        ("NEXT ACTION", "where certified follow-up should go"),
    ]
    for side, items in [("left", inputs), ("right", outputs)]:
        x = 3 if side == "left" else 73
        text_x = 5 if side == "left" else 75
        for i, (title, body) in enumerate(items):
            y = 43 - i * 11
            _card(ax, x, y - 5.5, 24, 8.3, color=PANEL, radius=1.2)
            ax.text(text_x, y, title, color=TEAL if side == "left" else WARM,
                    fontsize=11, weight="bold", va="center")
            ax.text(text_x, y - 2.4, body, color=WHITE, fontsize=9.5, va="center")
            start = (27.6, y - 1.3) if side == "left" else (69.4, y - 1.3)
            end = (31.0, y - 1.3) if side == "left" else (73.0, y - 1.3)
            ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=13,
                                         lw=1.5, color=TEAL if side == "left" else WARM))
    _save(fig, out / "digital_twin_simple.png")


def adaptive_comparison(out):
    fig, ax = plt.subplots(figsize=(16, 9))
    _style_figure(fig, ax)
    ax.text(50, 52.2, "EQUAL EVIDENCE BUDGET", ha="center", color=TEAL,
            fontsize=13, weight="bold")
    ax.text(50, 48.7, "48 readings  |  300 m travel cap  |  same area, plume and noise  |  8 seeds",
            ha="center", color=WHITE, fontsize=16, weight="bold")

    cards = [
        (4, "SPARSE FIXED", "Samples only at preset stations", "Boundary IoU 0.00", "0 / 8 conclusive", MUTED),
        (36, "REGULAR SURVEY", "Covers space evenly", "Boundary IoU 0.18", "4 / 8 conclusive", CYAN),
        (68, "BRINEWATCH ADAPTIVE", "Spends evidence near the boundary", "Boundary IoU 0.66", "8 / 8 conclusive", TEAL),
    ]
    for idx, (x, title, body, metric, conclusion, accent) in enumerate(cards):
        _card(ax, x, 9, 28, 34, color=PANEL, radius=2.0, edge=accent)
        ax.text(x + 2.2, 39.2, title, color=accent, fontsize=12, weight="bold")
        ax.text(x + 2.2, 36.2, body, color=WHITE, fontsize=10.5)

        # Common plume shape.
        gx = np.linspace(-2, 2, 100)
        gy = np.linspace(-1.1, 1.1, 60)
        xx, yy = np.meshgrid(gx, gy)
        plume = np.exp(-((xx - .3) / 1.15) ** 2 - (yy / .45) ** 2)
        ax.imshow(plume, extent=(x + 2, x + 26, 19, 32.5), origin="lower",
                  cmap="turbo", vmin=0, vmax=1, alpha=.92, zorder=2)

        if idx == 0:
            px = np.linspace(x + 4, x + 24, 6)
            py = np.array([21.5, 29.5, 21.5, 29.5])
            for yy0 in py:
                ax.scatter(px, np.full_like(px, yy0), s=20, color=WHITE, edgecolor=BG,
                           linewidth=.5, zorder=3)
        elif idx == 1:
            for j, yy0 in enumerate(np.linspace(20.5, 31, 8)):
                xx0 = [x + 3, x + 25] if j % 2 == 0 else [x + 25, x + 3]
                ax.plot(xx0, [yy0, yy0], color=WHITE, lw=1.15, alpha=.9, zorder=3)
                ax.scatter(np.linspace(x + 4, x + 24, 6), np.full(6, yy0), s=10,
                           color=WHITE, zorder=3)
        else:
            t = np.linspace(0, 1, 48)
            px = x + 4 + 20 * t
            py = 25.5 + 4.0 * np.sin(4 * np.pi * t) * (1 - .4 * t)
            ax.plot(px, py, color=WHITE, lw=1.5, zorder=3)
            ax.scatter(px, py, s=12, color=WHITE, zorder=3)

        ax.text(x + 2.2, 15.0, metric, color=WHITE, fontsize=15, weight="bold")
        ax.text(x + 2.2, 11.7, conclusion, color=accent, fontsize=12, weight="bold")
    ax.text(50, 4.4,
            "Practical result: adaptive sampling found the boundary with the same number of readings.",
            ha="center", color=WARM, fontsize=15, weight="bold")
    ax.text(95, 1.5, "Sampling patterns are illustrative; metrics are computed benchmark results.",
            ha="right", color=MUTED, fontsize=8.5)
    _save(fig, out / "adaptive_comparison_simple.png")


def grade_underwater(frame):
    x = frame.astype(np.float32) / 255.0
    x = np.clip((x - .5) * 1.20 + .43, 0, 1)
    x = np.power(x, 1.03)
    out = np.uint8(np.clip(x * 255, 0, 255))
    hsv = cv2.cvtColor(out, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 1.06, 0, 255)
    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)


def mission_stills(source, out):
    times = [2.6, 7.8, 12.8, 18.5, 15.5, 20.2]
    names = ["descent", "approach", "inspection", "diffuser", "result", "final"]
    cap = cv2.VideoCapture(str(source))
    if not cap.isOpened():
        raise FileNotFoundError(source)
    for t, name in zip(times, names):
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        if not ok:
            raise RuntimeError(f"Could not read {source} at {t}s")
        frame = grade_underwater(frame)
        cv2.imwrite(str(out / f"mission_{name}.jpg"), frame,
                    [cv2.IMWRITE_JPEG_QUALITY, 95])
    cap.release()


def _contain_on_canvas(image, size=(1600, 900), pad=28):
    w, h = size
    canvas = np.full((h, w, 3), (29, 23, 6), dtype=np.uint8)
    ih, iw = image.shape[:2]
    scale = min((w - 2 * pad) / iw, (h - 2 * pad) / ih)
    nw, nh = int(iw * scale), int(ih * scale)
    resized = cv2.resize(image, (nw, nh), interpolation=cv2.INTER_AREA)
    x, y = (w - nw) // 2, (h - nh) // 2
    canvas[y:y + nh, x:x + nw] = resized
    return canvas


def result_vignettes(assets, out):
    sonar = cv2.imread(str(assets / "sonar_localization.png"))
    mission = cv2.imread(str(out / "mission_result.jpg"))
    plume = cv2.imread(str(assets / "mission_reconstruction.png"))
    volume = cv2.imread(str(assets / "plume_3d.png"))
    if any(image is None for image in [sonar, mission, plume, volume]):
        raise FileNotFoundError("One or more source result images are missing")

    # Real sonar evidence: keep the residual image and independent geometry fit.
    sonar_focus = sonar[350:1380, 60:2780]
    # One reconstruction view only: focus on the adaptive map and boundary.
    plume_focus = plume[390:1325, 940:1895]
    # One volume view only: remove the original header and metric column.
    volume_focus = volume[420:1490, 180:2180]
    results = {
        "result_sonar.png": sonar_focus,
        "result_mission.png": mission,
        "result_2d.png": plume_focus,
        "result_3d.png": volume_focus,
    }
    for name, image in results.items():
        cv2.imwrite(str(out / name), _contain_on_canvas(image),
                    [cv2.IMWRITE_PNG_COMPRESSION, 6])


def clean_2d_result(npz_path, out):
    if not npz_path.exists():
        return
    data = np.load(npz_path)
    mean = data["mean"]
    x = data["X"]
    y = data["Y"]
    trajectory = data["trajectory"]
    threshold = 40.894

    fig, ax = plt.subplots(figsize=(16, 9))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    levels = np.linspace(float(np.nanmin(mean)), float(np.nanmax(mean)), 18)
    image = ax.contourf(x, y, mean, levels=levels, cmap="turbo")
    ax.contour(x, y, mean, levels=[threshold], colors=[WHITE], linewidths=3.0)
    ax.plot(trajectory[:, 1], trajectory[:, 2], color=WHITE, lw=1.6, alpha=.72)
    stride = max(1, len(trajectory) // 42)
    ax.scatter(trajectory[::stride, 1], trajectory[::stride, 2], s=26,
               color=TEAL, edgecolor=BG, linewidth=.5, zorder=4)
    ax.scatter([30], [0], marker="*", s=320, color=CORAL, edgecolor=BG,
               linewidth=1.5, zorder=5)
    ax.add_patch(Circle((30, 0), 22, facecolor="none", edgecolor=WARM,
                        lw=2.0, ls=(0, (6, 5))))
    ax.set_xlim(18, 78)
    ax.set_ylim(-28, 28)
    ax.set_aspect("equal")
    ax.tick_params(colors=MUTED, labelsize=12)
    for spine in ax.spines.values():
        spine.set_color("#1f5663")
    ax.grid(color="#24505a", alpha=.34)
    ax.set_xlabel("x (m)", color=MUTED, fontsize=13)
    ax.set_ylabel("y (m)", color=MUTED, fontsize=13)
    ax.set_title("Adaptive reconstruction and sampled route", color=WHITE,
                 fontsize=22, weight="bold", pad=18)
    cbar = fig.colorbar(image, ax=ax, orientation="horizontal", pad=.12,
                        fraction=.06, aspect=34)
    cbar.set_label("reconstructed salinity (PSU)", color=MUTED, fontsize=12)
    cbar.ax.tick_params(colors=MUTED, labelsize=10)
    fig.tight_layout(pad=2.0)
    _save(fig, out / "result_2d.png")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--cinematic",
        default=r"C:\bwrt\bwp26-cin1\outputs\cinematic_1080p\BrineWatch_HoloOcean_Continuous_1080p_Source.mp4",
    )
    ap.add_argument("--source-assets", default=str(ROOT / "output" / "fasttrack" / "assets"))
    ap.add_argument("--out", default=str(ROOT / "output" / "redesign" / "assets"))
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    source_assets = Path(args.source_assets)
    problem_diagram(out)
    digital_twin_diagram(out)
    adaptive_comparison(out)
    mission_stills(Path(args.cinematic), out)
    result_vignettes(source_assets, out)
    clean_2d_result(
        ROOT / ".runtime" / "fasttrack" / "screening" /
        "brinewatch_pfh2026_flagship_demo_adaptive_kinematic_20260722_091838" /
        "plume_maps.npz",
        out,
    )
    print(f"[public-assets] {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

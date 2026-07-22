"""Render a Full-HD progressive reveal of the final 3-D plume posterior."""
from __future__ import annotations

import argparse
import json
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

from brinewatch.utils.config import load_config
from scripts.build_fasttrack_visuals import (
    BG, CYAN, MUTED, RED, TEAL, TEXT, draw_3d)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--volume", default=str(REPO / ".runtime" / "fasttrack" /
                    "volumetric" / "volumetric_adaptive_20260722_094757"))
    ap.add_argument("--config", default=str(
        REPO / "configs" / "pfh2026_flagship_volumetric.yaml"))
    ap.add_argument("--out", default=str(ROOT / "output" / "fasttrack" / "video_sources"))
    ap.add_argument("--frames", type=int, default=60,
                    help="unique frames; each is repeated four times at 30 fps")
    args = ap.parse_args()
    run, out = Path(args.volume), Path(args.out)
    stills = out / "plume_animation_keyframes"
    stills.mkdir(parents=True, exist_ok=True)
    data = np.load(run / "volume.npz")
    cfg = load_config(args.config)
    summary = json.loads((run / "volumetric_summary.json").read_text(encoding="utf-8"))
    path = out / "BrineWatch_3D_Plume_Progressive_1080p.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"),
                             30, (1920, 1080))
    if not writer.isOpened():
        raise RuntimeError("could not open 3-D animation writer")
    for idx in range(args.frames):
        u = idx / max(1, args.frames - 1)
        sample_fraction = min(1.0, .04 + 1.65 * u)
        trajectory_fraction = min(1.0, .05 + 1.45 * u)
        surface_alpha = max(0.0, min(.62, (u - .18) * .92))
        show_uncertainty = u >= .42
        azim = -67 + 31 * u
        if u < .34:
            stage = "1  SAMPLES ARRIVE ACROSS FOUR ALTITUDE BANDS"
        elif u < .68:
            stage = "2  ONE ANISOTROPIC 3-D GP FORMS THE VOLUME"
        else:
            stage = "3  ISOHALINE + CONFIDENCE GUIDE THE NEXT MISSION"
        fig = plt.figure(figsize=(16, 9), dpi=120, facecolor=BG)
        ax = fig.add_axes([.03, .08, .77, .80], projection="3d")
        draw_3d(ax, data, cfg, azim=azim, surface_alpha=surface_alpha,
                sample_fraction=sample_fraction,
                trajectory_fraction=trajectory_fraction,
                show_uncertainty=show_uncertainty)
        fig.text(.055, .94, "BRINEWATCH | 3-D DIGITAL TWIN UPDATE",
                 color=TEAL, fontsize=12, weight="bold")
        fig.text(.055, .885, stage, color=TEXT, fontsize=20, weight="bold")
        fig.text(.805, .72, "THRESHOLD", color=MUTED, fontsize=9, weight="bold")
        fig.text(.805, .675, f"{float(data['threshold']):.2f} PSU",
                 color=TEXT, fontsize=19, weight="bold")
        fig.text(.805, .55, "VOLUME IoU", color=MUTED, fontsize=9, weight="bold")
        fig.text(.805, .505, f"{summary['reconstruction']['volume_iou']:.2f}",
                 color=TEAL, fontsize=22, weight="bold")
        fig.text(.805, .38, "3-D RMSE", color=MUTED, fontsize=9, weight="bold")
        fig.text(.805, .335, f"{summary['reconstruction']['rmse_psu']:.3f} PSU",
                 color=CYAN, fontsize=19, weight="bold")
        fig.text(.805, .19,
                 "Gold: confident core\nCyan: possible extent\nRed: ROV trajectory",
                 color=MUTED, fontsize=10, linespacing=1.5)
        fig.text(.805, .08, "Analytic simulation surrogate\nnot CFD or field truth",
                 color=RED, fontsize=9, linespacing=1.35)
        fig.canvas.draw()
        rgba = np.asarray(fig.canvas.buffer_rgba())
        bgr = cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGR)
        for _ in range(4):
            writer.write(bgr)
        if idx in {0, args.frames // 3, 2 * args.frames // 3, args.frames - 1}:
            cv2.imwrite(str(stills / f"plume_{idx:03d}.png"), bgr)
        plt.close(fig)
        if idx % 10 == 0:
            print(f"[plume-animation] {idx}/{args.frames}")
    writer.release()
    manifest = {
        "file": str(path.resolve()), "resolution": [1920, 1080],
        "fps": 30, "frames": args.frames * 4,
        "duration_s": args.frames * 4 / 30,
        "content": ("progressive reveal of recorded samples, altitude bands, "
                    "final anisotropic GP posterior, reconstructed threshold "
                    "surface and uncertainty bounds"),
        "disclosure": ("presentation animation of the final simulation "
                       "posterior; not a claim of live field telemetry"),
    }
    (out / "plume_animation_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"[plume-animation] DONE {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

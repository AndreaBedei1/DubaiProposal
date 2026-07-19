"""Cinematic inspection flythrough of the BrineWatch outfall (Demo 2).

A smooth free-camera (move_viewport + ViewportCapture) dolly through the
accepted outfall scene: wide establishing -> descend -> approach the
pipeline -> follow the pipe -> inspect the risers/nozzles -> slow orbit ->
pull back. Frames are captured at smoothly interpolated camera poses (no
physics jitter, no clipping), plus a camera-pose log, a phase log, a contact
sheet, and (if ffmpeg is present) an MP4.

Default: the OFFICIAL engine at the accepted Dam site (materials render), so
the structure looks its best. The plume/CTD are not involved; this is the
visual showcase. Sonar contacts for the video come from the custom-engine
sonar runs (composited separately; see the storyboard).

Usage:
    python scripts/capture_cinematic_inspection.py
    python scripts/capture_cinematic_inspection.py --world Dam --site -100 -35 --yaw 165 --bed -65.9
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

AGENT = "cam"


def smoothstep(t):
    return t * t * (3 - 2 * t)


def interpolate(keys, frames_per_leg):
    """Piecewise smoothstep interpolation of (pos, look, phase) keyframes."""
    out = []
    for i in range(len(keys) - 1):
        (p0, l0, ph), (p1, l1, _) = keys[i], keys[i + 1]
        for f in range(frames_per_leg):
            t = smoothstep(f / frames_per_leg)
            pos = [p0[j] + (p1[j] - p0[j]) * t for j in range(3)]
            look = [l0[j] + (l1[j] - l0[j]) * t for j in range(3)]
            out.append((pos, look, ph))
    out.append((keys[-1][0], keys[-1][1], keys[-1][2]))
    return out


def look_rot(pos, look):
    """[roll, pitch, yaw] (deg) for a camera at pos looking at look."""
    dx, dy, dz = look[0] - pos[0], look[1] - pos[1], look[2] - pos[2]
    yaw = math.degrees(math.atan2(dy, dx))
    pitch = math.degrees(math.atan2(dz, math.hypot(dx, dy)))
    return [0.0, pitch, yaw]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--world", default="Dam")
    ap.add_argument("--site", type=float, nargs=2, default=(-100.0, -35.0))
    ap.add_argument("--yaw", type=float, default=165.0)
    ap.add_argument("--bed", type=float, default=-65.9)
    ap.add_argument("--frames-per-leg", type=int, default=24)
    ap.add_argument("--res", type=int, nargs=2, default=(1280, 720))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    import holoocean
    from brinewatch.simulation.outfall_scene import (
        OutfallSceneBuilder, OutfallSceneConfig)
    from brinewatch.utils.config import OutfallConfig
    from brinewatch.utils.terrain import TerrainMap

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path(args.out) if args.out else REPO / "outputs" / f"cinematic_{args.world}_{stamp}"
    frames_dir = out / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    ox, oy = args.site
    W, H = args.res
    scenario = {
        "name": "cinematic", "world": args.world, "package_name": "Ocean",
        "main_agent": AGENT, "ticks_per_sec": 30, "frames_per_sec": False,
        "agents": [{
            "agent_name": AGENT, "agent_type": "BlueROV2",
            "sensors": [
                {"sensor_type": "LocationSensor", "socket": "IMUSocket"},
                {"sensor_type": "RangeFinderSensor", "socket": "SonarSocket",
                 "configuration": {"LaserCount": 4, "LaserAngle": -90,
                                   "LaserMaxDistance": 200}},
                {"sensor_type": "ViewportCapture",
                 "configuration": {"CaptureWidth": W, "CaptureHeight": H}},
            ],
            "control_scheme": 1,
            "location": [ox + 35.0, oy - 35.0, -8.0],
            "rotation": [0.0, 0.0, 135.0],
        }],
        "window_width": W, "window_height": H,
    }
    env = holoocean.make(scenario_cfg=scenario, show_viewport=True, verbose=False)
    agent = env.agents[AGENT]
    print(f"[cinematic] {args.world} up")

    # terrain probe + scene build (same accepted geometry, materials on official)
    def bed_at(x, y):
        for hz in (args.bed + 3.0, -30.0, -80.0, -150.0):
            cmd = np.array([x, y, hz, 0.0, 0.0, 0.0], dtype=np.float64)
            state = None
            for _ in range(10):
                agent.teleport([x, y, hz], [0.0, 0.0, 0.0])
                env.act(AGENT, cmd)
                state = env.tick()
            rf = np.asarray(state["RangeFinderSensor"], dtype=float)
            loc = np.asarray(state["LocationSensor"], dtype=float)
            v = rf[rf > 0.5]
            if v.size:
                return float(loc[2]) - float(v.min())
        return args.bed

    lx = np.linspace(ox - 40, ox + 40, 9)
    ly = np.linspace(oy - 40, oy + 40, 9)
    lz = np.full((9, 9), np.nan)
    for i, x in enumerate(lx):
        for j, y in enumerate(ly):
            lz[j, i] = bed_at(float(x), float(y))
    terrain = TerrainMap(lx, ly, np.nan_to_num(lz, nan=args.bed))
    builder = OutfallSceneBuilder(
        env=env, agent_name=AGENT,
        outfall=OutfallConfig(x=ox, y=oy, axis_deg=args.yaw, n_ports=6,
                              port_spacing_m=3.2),
        scene=OutfallSceneConfig(structure_yaw_deg=args.yaw, scatter_rocks=0),
        terrain=terrain)
    builder.build()
    bed0 = float(np.nanmedian(lz))
    print(f"[cinematic] scene built, bed {bed0:.1f}")

    # camera keyframes in the LOCAL structure frame -> world
    sc = builder.scene
    L = sc.diffuser_length_m
    mid = L / 2.0

    def w(s, t, h):
        wx, wy = builder.to_world(s, t)
        return [wx, wy, builder.bed(s, t) + h]

    # (camera pos, look-at, phase)
    keys = [
        (w(mid, 34, 22), w(mid, 0, 1), "01_establishing"),
        (w(mid, 22, 13), w(mid, 0, 1), "02_descend"),
        (w(-34, 12, 5), w(-18, 0, 1), "03_approach_pipeline"),
        (w(-14, 7, 3), w(2, 0, 1), "04_follow_pipe"),
        (w(mid - 2, 5.5, 2.4), w(mid, 0, 1.6), "05_inspect_risers"),
        (w(L + 3, 5.5, 2.4), w(L - 3, 0, 1.4), "06_inspect_nozzles"),
        (w(L + 12, 10, 4), w(mid, 0, 1), "07_orbit_out"),
        (w(mid, -16, 7), w(mid, 0, 1), "08_orbit_far"),
        (w(mid, 30, 16), w(mid, 0, 1), "09_pull_back"),
    ]
    path = interpolate(keys, args.frames_per_leg)

    poses_log = []
    contact_imgs = []
    seen_phase = set()
    for idx, (pos, look, phase) in enumerate(path):
        rot = look_rot(pos, look)
        env.move_viewport(pos, rot)
        state = None
        for _ in range(6):
            state = env.tick()
        rgb = np.asarray(state["ViewportCapture"])[:, :, :3][:, :, ::-1]
        mean_px = float(rgb.mean())
        fp = frames_dir / f"frame_{idx:04d}.png"
        plt.imsave(fp, rgb.astype(np.uint8))
        poses_log.append({"frame": idx, "phase": phase,
                          "pos": [round(v, 2) for v in pos],
                          "look": [round(v, 2) for v in look],
                          "pixel_mean": round(mean_px, 1)})
        if phase not in seen_phase and mean_px > 40:
            seen_phase.add(phase)
            contact_imgs.append((phase, rgb))
        if idx % 12 == 0:
            print(f"[cinematic] frame {idx}/{len(path)} ({phase}) mean {mean_px:.0f}")

    (out / "camera_log.json").write_text(json.dumps(poses_log, indent=2),
                                         encoding="utf-8")

    # contact sheet (one frame per phase)
    n = len(contact_imgs)
    if n:
        cols = 3
        rows = (n + cols - 1) // cols
        fig, axes = plt.subplots(rows, cols, figsize=(5.2 * cols, 3.0 * rows))
        for ax, (ph, im) in zip(np.atleast_1d(axes).ravel(), contact_imgs):
            ax.imshow(im)
            ax.set_title(ph, fontsize=9)
            ax.axis("off")
        for ax in np.atleast_1d(axes).ravel()[n:]:
            ax.axis("off")
        fig.suptitle(f"Cinematic inspection - {args.world} (genuine HoloOcean captures)")
        fig.tight_layout()
        fig.savefig(out / "contact_sheet.png", dpi=110)
        plt.close(fig)

    # assemble MP4 (OpenCV; no ffmpeg needed)
    try:
        import cv2
        files = sorted(frames_dir.glob("frame_*.png"))
        if files:
            h, w = plt.imread(files[0]).shape[:2]
            vw = cv2.VideoWriter(str(out / "cinematic.mp4"),
                                 cv2.VideoWriter_fourcc(*"mp4v"), 24, (w, h))
            for f in files:
                img = cv2.imread(str(f))
                vw.write(img)
            vw.release()
            print(f"[cinematic] MP4: {out / 'cinematic.mp4'}")
    except Exception as exc:
        print(f"[cinematic] MP4 assembly skipped ({exc}); frames saved")

    print(f"[cinematic] DONE -> {out} ({len(path)} frames)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

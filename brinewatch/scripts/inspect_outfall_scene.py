"""Iterative visual inspection of the multiport outfall scene.

Boots PierHarbor, builds the outfall (terrain probe or a saved terrain.npz),
then moves the camera vehicle through a structured set of viewpoints defined
in the STRUCTURE's local frame, capturing genuine RGB frames:

 1 wide establishing        6 supports / seabed contact
 2 elevated oblique         7 ROV-scale close riser
 3 low side along pipe      8 top-down engineering
 4 three-quarter risers     9 mission approach aspect
 5 close nozzles           10 departure aspect

Each frame is checked against black-frame failures (pixel mean), poses are
logged, and a contact sheet is rendered for one-glance judgement.

Usage:
    python scripts/inspect_outfall_scene.py [--terrain <terrain.npz>]
        [--config configs/pfh2026_holoocean.yaml] [--tag iterN]
"""
from __future__ import annotations

import argparse
import datetime
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from brinewatch.simulation.outfall_scene import OutfallSceneBuilder, OutfallSceneConfig
from brinewatch.utils.config import load_config
from brinewatch.utils.terrain import TerrainMap

WORLD = "PierHarbor"
AGENT = "inspector"


def guard_single_engine() -> None:
    res = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Holodeck.exe"],
                         capture_output=True, text=True)
    if "Holodeck" in res.stdout:
        raise SystemExit("another Holodeck engine is running; close it first "
                         "(black-frame failure mode, see SCENE_ITERATION_LOG)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", type=str,
                    default=str(REPO_ROOT / "configs" / "pfh2026_holoocean.yaml"))
    ap.add_argument("--terrain", type=str, default=None)
    ap.add_argument("--tag", type=str, default="iter")
    ap.add_argument("--yaw", type=float, default=None,
                    help="override structure yaw (deg)")
    ap.add_argument("--world", type=str, default=None, help="override world")
    ap.add_argument("--site", type=float, nargs=2, default=None,
                    metavar=("X", "Y"), help="override outfall origin")
    ap.add_argument("--bed", type=float, default=None,
                    help="reference bed z for the terrain probe")
    args = ap.parse_args()

    guard_single_engine()
    import dataclasses

    import holoocean

    cfg = load_config(args.config)
    if args.site is not None:
        cfg = dataclasses.replace(cfg, outfall=dataclasses.replace(
            cfg.outfall, x=args.site[0], y=args.site[1]))
    if args.bed is not None:
        cfg = dataclasses.replace(cfg, environment=dataclasses.replace(
            cfg.environment, seabed_z0=args.bed))
    world = args.world or WORLD
    ox, oy = cfg.outfall.x, cfg.outfall.y

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out = REPO_ROOT / "outputs" / f"outfall_inspection_{args.tag}_{stamp}"
    out.mkdir(parents=True, exist_ok=True)

    scene_cfg = OutfallSceneConfig()
    if args.yaw is not None:
        scene_cfg.structure_yaw_deg = args.yaw

    scenario = {
        "name": "outfall_inspection", "package_name": "Ocean", "world": world,
        "main_agent": AGENT, "ticks_per_sec": 30, "frames_per_sec": False,
        "agents": [{
            "agent_name": AGENT, "agent_type": "BlueROV2",
            "sensors": [
                {"sensor_type": "PoseSensor", "socket": "IMUSocket"},
                {"sensor_type": "LocationSensor", "socket": "IMUSocket"},
                {"sensor_type": "RangeFinderSensor", "socket": "SonarSocket",
                 "configuration": {"LaserCount": 4, "LaserAngle": -90,
                                   "LaserMaxDistance": 80}},
                {"sensor_type": "RGBCamera", "socket": "CameraSocket",
                 "configuration": {"CaptureWidth": 960, "CaptureHeight": 540}},
                # free-camera capture for plan views (the ROV cannot hold
                # steep pitch); dimensions MUST match window_width/height
                {"sensor_type": "ViewportCapture",
                 "configuration": {"CaptureWidth": 800, "CaptureHeight": 450}},
            ],
            "control_scheme": 1,
            # boot in verified open water, never against structures
            "location": [ox + 30.0, oy - 30.0, -10.0],
            "rotation": [0.0, 0.0, 135.0],
        }],
        "window_width": 800, "window_height": 450,
    }
    env = holoocean.make(scenario_cfg=scenario, show_viewport=True, verbose=False)
    agent = env.agents[AGENT]

    upstream = math.radians(cfg.environment.current_dir_deg + 180.0)
    builder = OutfallSceneBuilder(env=env, agent_name=AGENT, outfall=cfg.outfall,
                                  scene=scene_cfg, upstream_dir_rad=upstream)
    if args.terrain:
        builder.terrain = TerrainMap.from_npz(args.terrain)
    else:
        builder.probe_terrain(reference_bed_z=cfg.environment.seabed_z0)
        builder.terrain.save_npz(out / "terrain.npz")
    if args.yaw is None and scene_cfg.structure_yaw_deg is None:
        builder.auto_orient()
    builder.build()
    builder.save_manifest(out / "scene_manifest.json")

    sc = builder.scene
    L = sc.diffuser_length_m
    mid = L / 2.0
    bed0 = builder.bed(mid)

    # (name, local s, local t, height above bed, look-at local (s, t, h))
    views = [
        ("01_wide_establishing", -6.0, 26.0, 9.0, (mid * 0.4, 0.0, 1.0)),
        ("02_elevated_oblique", -14.0, 15.0, 11.0, (mid, 0.0, 0.5)),
        ("03_low_side_along_pipe", -24.0, 3.6, 1.4, (0.0, 0.0, 1.0)),
        ("04_three_quarter_risers", L + 9.0, 6.5, 2.6, (L - 4.0, 0.0, 1.2)),
        ("05_close_nozzles", mid, 3.4, 2.4, (mid, 0.0, 1.9)),
        ("06_supports_contact", 2.0, 5.0, 1.0, (1.0, 0.0, 0.6)),
        ("07_rov_scale_riser", sc.diffuser_margin_m, 2.4, 1.3,
         (sc.diffuser_margin_m, 0.0, 1.4)),
        # rendered via the free viewport camera (see below): the BlueROV2
        # cannot hold pitch steeper than about -25 deg
        ("08_plan_view", mid, -15.0, 26.0, (mid, 0.0, 0.0)),
        ("09_mission_approach", -40.0, -6.0, 3.0, (-10.0, 0.0, 1.0)),
        ("10_departure", L + 16.0, -8.0, 4.0, (L, 0.0, 1.0)),
    ]

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    poses = {}
    images = []
    for name, s, t, h, look in views:
        px, py = builder.to_world(s, t)
        pz = builder.bed(s, t) + h
        lx, ly = builder.to_world(look[0], look[1])
        lz = builder.bed(look[0], look[1]) + look[2]
        yaw = math.degrees(math.atan2(ly - py, lx - px))
        dist = math.hypot(lx - px, ly - py)
        pitch = -math.degrees(math.atan2(pz - lz, max(dist, 1e-3)))
        if name.startswith("08_"):
            # steep plan view: free viewport camera, not the agent
            env.move_viewport([px, py, pz], [0.0, pitch, yaw])
            state = None
            for _ in range(12):
                state = env.tick()
            rgb = np.asarray(state["ViewportCapture"])[:, :, :3][:, :, ::-1]
        else:
            cmd = np.array([px, py, pz, 0.0, pitch, yaw], dtype=np.float64)
            agent.teleport([px, py, pz], [0.0, pitch, yaw])
            state = None
            for _ in range(45):
                env.act(AGENT, cmd)
                state = env.tick()
            rgb = np.asarray(state["RGBCamera"])[:, :, :3][:, :, ::-1]
        mean_px = float(rgb.mean())
        if mean_px < 2.0:
            raise SystemExit(f"black frame at view '{name}' — aborting loudly")
        path = out / f"{name}.png"
        plt.imsave(path, rgb.astype(np.uint8))
        poses[name] = {"pos": [round(px, 1), round(py, 1), round(pz, 1)],
                       "yaw_deg": round(yaw, 1), "pitch_deg": round(pitch, 1),
                       "pixel_mean": round(mean_px, 1)}
        images.append((name, rgb))
        print(f"[inspect] {name}: pixel mean {mean_px:.0f}")

    # ---- contact sheet ---------------------------------------------------- #
    fig, axes = plt.subplots(2, 5, figsize=(22, 5.6), constrained_layout=True)
    for ax, (name, rgb) in zip(axes.ravel(), images):
        ax.imshow(rgb)
        ax.set_title(name, fontsize=8)
        ax.axis("off")
    fig.suptitle(f"Outfall inspection — {args.tag} ({stamp}) — genuine HoloOcean "
                 f"RGB captures, world {world}", fontsize=11)
    fig.savefig(out / "contact_sheet.png", dpi=110)
    plt.close(fig)

    (out / "poses.json").write_text(json.dumps(poses, indent=2), encoding="utf-8")
    print(f"[inspect] DONE -> {out}")
    print(f"[inspect] contact sheet: {out / 'contact_sheet.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

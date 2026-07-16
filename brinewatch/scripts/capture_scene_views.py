"""Capture application-quality views of the outfall scene (official HoloOcean).

Boots PierHarbor, rebuilds the outfall scene on the measured terrain (reusing
a saved terrain.npz from a demo run when available), then teleports the
camera vehicle through the required viewpoints and saves genuine RGB captures:

1. overview of the outfall area (elevated oblique)
2. side view showing pipe and diffuser
3. ROV-approach view (low, along the pipe)
4. close view of the diffuser risers
5. clean wide shot (no overlays)
6. context shot with the pier structure behind the outfall

Technical annotated variants are produced post-hoc by
scripts/annotate_scene_views.py (matplotlib overlays on the genuine frames,
clearly annotations rather than simulator output).

Usage:
    python scripts/capture_scene_views.py [--terrain outputs/<run>/terrain.npz]
"""
from __future__ import annotations

import argparse
import datetime
import json
import math
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from brinewatch.simulation.outfall_scene import OutfallSceneBuilder, OutfallSceneConfig
from brinewatch.utils.config import load_config
from brinewatch.utils.terrain import TerrainMap

WORLD = "PierHarbor"
AGENT = "camera_rig"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", type=str,
                    default=str(REPO_ROOT / "configs" / "pfh2026_holoocean.yaml"))
    ap.add_argument("--terrain", type=str, default=None,
                    help="terrain.npz from a demo run (else a fresh probe is made)")
    args = ap.parse_args()

    import holoocean

    # Single-engine guard: booting while another Holodeck instance is alive
    # (even one still shutting down) yields black camera frames with working
    # sensors — verified empirically (see SCENE_ITERATION_LOG.md).
    try:
        import psutil  # type: ignore

        for proc in psutil.process_iter(["name"]):
            if (proc.info["name"] or "").lower().startswith("holodeck"):
                raise SystemExit(
                    "another Holodeck engine is running (PID "
                    f"{proc.pid}); close it before capturing scene views")
    except ImportError:
        import subprocess

        res = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Holodeck.exe"],
                             capture_output=True, text=True)
        if "Holodeck" in res.stdout:
            raise SystemExit("another Holodeck engine is running; close it "
                             "before capturing scene views")

    cfg = load_config(args.config)
    out_cfg = cfg.outfall
    ox, oy = out_cfg.x, out_cfg.y

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out = REPO_ROOT / "outputs" / f"scene_views_{stamp}"
    out.mkdir(parents=True, exist_ok=True)

    scenario = {
        "name": "scene_views", "package_name": "Ocean", "world": WORLD,
        "main_agent": AGENT, "ticks_per_sec": 30, "frames_per_sec": False,
        "agents": [{
            "agent_name": AGENT, "agent_type": "BlueROV2",
            "sensors": [
                {"sensor_type": "PoseSensor", "socket": "IMUSocket"},
                {"sensor_type": "LocationSensor", "socket": "IMUSocket"},
                {"sensor_type": "RangeFinderSensor", "socket": "SonarSocket",
                 "configuration": {"LaserCount": 4, "LaserAngle": -90,
                                   "LaserMaxDistance": 80}},
                # NOTE (scene iteration log): 1600x900 returned all-black
                # frames on this machine; 960x540 renders correctly.
                {"sensor_type": "RGBCamera", "socket": "CameraSocket",
                 "configuration": {"CaptureWidth": 960, "CaptureHeight": 540}},
            ],
            "control_scheme": 1,
            # NOTE (scene iteration log): booting at (outfall_x, outfall_y-20)
            # placed the vehicle against a stock obstacle (the same one the v6
            # mission bumped at ~(457,-645)) and every subsequent camera frame
            # came back black; boot in verified open water instead.
            "location": [ox + 18.0, oy - 26.0, -12.0], "rotation": [0.0, 0.0, 120.0],
        }],
        # NOTE (scene iteration log): with window 1280x720 the RGBCamera
        # returns black frames on this machine; 800x450 renders correctly
        # (window and capture buffers appear to contend).
        "window_width": 800, "window_height": 450,
    }

    env = holoocean.make(scenario_cfg=scenario, show_viewport=True, verbose=False)
    agent = env.agents[AGENT]
    upstream = math.radians(cfg.environment.current_dir_deg + 180.0)
    builder = OutfallSceneBuilder(env=env, agent_name=AGENT, outfall=out_cfg,
                                  scene=OutfallSceneConfig(),
                                  upstream_dir_rad=upstream)
    if args.terrain:
        builder.terrain = TerrainMap.from_npz(args.terrain)
        print(f"[scene_views] terrain loaded from {args.terrain}")
    else:
        builder.probe_terrain(reference_bed_z=cfg.environment.seabed_z0)
    builder.build()
    builder.save_manifest(out / "scene_manifest.json")
    bed = builder._bed(ox, oy)

    def yaw_towards(px, py, tx, ty):
        return math.degrees(math.atan2(ty - py, tx - px))

    views = [
        # (name, position, look-at point)
        ("overview_oblique", (ox + 18.0, oy - 26.0, bed + 14.0), (ox, oy, bed + 1.0)),
        ("side_pipe_diffuser", (ox + 16.0, oy - 8.0, bed + 2.5), (ox - 2.0, oy - 4.0, bed + 1.0)),
        ("rov_approach_along_pipe", (ox + 1.5, oy - 16.0, bed + 2.0), (ox, oy, bed + 1.5)),
        ("close_risers", (ox + 5.0, oy - 3.5, bed + 2.2), (ox, oy, bed + 1.8)),
        ("clean_wide", (ox - 14.0, oy - 18.0, bed + 6.0), (ox, oy, bed + 1.0)),
        ("context_pier_behind", (ox + 4.0, oy - 30.0, bed + 4.0), (ox, oy + 6.0, bed + 3.0)),
    ]

    captures = {}
    for name, pos, look in views:
        yaw = yaw_towards(pos[0], pos[1], look[0], look[1])
        # Camera pitch: approximate by pitching the whole vehicle
        dist = math.hypot(look[0] - pos[0], look[1] - pos[1])
        pitch = -math.degrees(math.atan2(pos[2] - look[2], max(dist, 1e-3)))
        cmd = np.array([*pos, 0.0, pitch, yaw], dtype=np.float64)
        agent.teleport(list(pos), [0.0, pitch, yaw])
        state = None
        for _ in range(45):  # settle + let rendering converge
            env.act(AGENT, cmd)
            state = env.tick()
        if "RGBCamera" in state:
            rgb = np.asarray(state["RGBCamera"])[:, :, :3][:, :, ::-1]
            mean_px = float(rgb.mean())
            if mean_px < 2.0:
                raise SystemExit(
                    f"black frame captured for '{name}' (pixel mean {mean_px:.1f}) "
                    "— rendering broken (engine overlap?); aborting loudly")
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            path = out / f"{name}.png"
            plt.imsave(path, rgb.astype(np.uint8))
            captures[name] = str(path)
            print(f"[scene_views] captured {name} (pixel mean {mean_px:.0f})")

    (out / "views.json").write_text(json.dumps(
        {"world": WORLD, "outfall": {"x": ox, "y": oy, "bed_z": bed},
         "captures": captures}, indent=2), encoding="utf-8")
    print(f"[scene_views] DONE -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

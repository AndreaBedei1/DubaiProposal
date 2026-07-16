"""Focused probe: what does the sonar actually see from the LOCATE area?

The first PFH demo's LOCATE detections clustered near (478, -637) — east of
the pier pilings mapped by the recon. This probe captures sonar + camera
from the prior position looking east, north-west (toward the mapped
pilings) and south, at survey altitude, to identify the acoustic source.
"""
from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

WORLD = "PierHarbor"
AGENT = "probe"
SONAR_CFG = {"RangeMin": 1.0, "RangeMax": 40.0, "RangeBins": 512,
             "AzimuthBins": 256, "Azimuth": 120.0, "Elevation": 20.0,
             "InitOctreeRange": 50.0, "ShowWarning": False}

# (name, xyz, yaw_deg) — z near survey altitude over the ~-20 m shelf
POSES = [
    ("east_from_prior", [466.0, -644.0, -18.0], 0.0),
    ("northwest_to_pilings", [466.0, -644.0, -18.0], 125.0),
    ("south_openshelf", [466.0, -644.0, -18.0], -90.0),
    ("at_detection_cluster_west", [490.0, -638.0, -18.0], 180.0),
]


def main() -> int:
    import holoocean

    from brinewatch.perception.sonar_diffuser_detector import SonarDiffuserDetector
    from brinewatch.sensors.sonar_types import SonarFrame

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out = REPO_ROOT / "outputs" / f"locate_probe_{stamp}"
    out.mkdir(parents=True, exist_ok=True)

    scenario = {
        "name": "locate_probe", "package_name": "Ocean", "world": WORLD,
        "main_agent": AGENT, "ticks_per_sec": 30, "frames_per_sec": False,
        "octree_min": 0.05, "octree_max": 5.0,
        "agents": [{
            "agent_name": AGENT, "agent_type": "BlueROV2",
            "sensors": [
                {"sensor_type": "PoseSensor", "socket": "IMUSocket"},
                {"sensor_type": "LocationSensor", "socket": "IMUSocket"},
                {"sensor_type": "ImagingSonar", "socket": "SonarSocket",
                 "configuration": dict(SONAR_CFG)},
                {"sensor_type": "RGBCamera", "socket": "CameraSocket",
                 "configuration": {"CaptureWidth": 800, "CaptureHeight": 450}},
            ],
            "control_scheme": 1,
            "location": POSES[0][1], "rotation": [0.0, 0.0, POSES[0][2]],
        }],
        "window_width": 800, "window_height": 450,
    }

    env = holoocean.make(scenario_cfg=scenario, show_viewport=True, verbose=False)
    agent = env.agents[AGENT]
    det = SonarDiffuserDetector()
    results = []

    for name, xyz, yaw in POSES:
        cmd = np.array([*xyz, 0.0, 0.0, yaw], dtype=np.float64)
        agent.teleport(list(xyz), [0.0, 0.0, yaw])
        state = None
        for _ in range(60):
            env.act(AGENT, cmd)
            state = env.tick()
        frames = []
        for _ in range(8):
            env.act(AGENT, cmd)
            state = env.tick()
            if "ImagingSonar" in state:
                frames.append(np.asarray(state["ImagingSonar"], dtype=np.float32))
        mean = np.stack(frames[-5:]).mean(axis=0)
        np.save(out / f"sonar_{name}.npy", mean)

        fig, ax = plt.subplots(figsize=(7, 5), constrained_layout=True)
        img = ax.imshow(np.log1p(mean), origin="lower", aspect="auto", cmap="inferno",
                        extent=[SONAR_CFG["Azimuth"] / 2, -SONAR_CFG["Azimuth"] / 2,
                                SONAR_CFG["RangeMin"], SONAR_CFG["RangeMax"]])
        ax.set_xlabel("Bearing (deg, +left)")
        ax.set_ylabel("Range (m)")
        ax.set_title(f"{name} (yaw {yaw:.0f})")
        fig.colorbar(img, ax=ax)
        fig.savefig(out / f"sonar_{name}.png", dpi=130)
        plt.close(fig)

        if "RGBCamera" in state:
            rgb = np.asarray(state["RGBCamera"])[:, :, :3][:, :, ::-1]
            plt.imsave(out / f"camera_{name}.png", rgb.astype(np.uint8))

        loc = np.asarray(state["LocationSensor"], dtype=float)
        pose = np.asarray(state["PoseSensor"], dtype=float)
        yaw_rad = float(np.arctan2(pose[1, 0], pose[0, 0]))
        frame = SonarFrame(t=0.0, image=mean, range_min_m=1.0, range_max_m=40.0,
                           azimuth_fov_deg=120.0, elevation_fov_deg=20.0,
                           vehicle_xyz=tuple(map(float, loc)),
                           vehicle_rpy=(0.0, 0.0, yaw_rad))
        contacts = det.detect(frame)
        entry = {"pose": name, "yaw_deg": yaw, "frame_max": float(mean.max()),
                 "contacts": [{"range_m": round(c.range_m, 1),
                               "bearing_deg": round(np.degrees(c.bearing_rad), 1),
                               "strength": round(c.strength, 1), "area": c.area_bins,
                               "est_world": [round(loc[0] + c.range_m * np.cos(yaw_rad + c.bearing_rad), 1),
                                             round(loc[1] + c.range_m * np.sin(yaw_rad + c.bearing_rad), 1)]}
                              for c in contacts]}
        results.append(entry)
        print(json.dumps(entry))

    (out / "summary.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"DONE -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

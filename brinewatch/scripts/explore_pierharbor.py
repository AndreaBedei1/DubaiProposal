"""Reconnaissance of PierHarbor as the PFH 2026 mission site.

Rationale: the sonar-visibility gate proved (bit-identical present/absent
frames, outputs/sonar_visibility_*) that runtime-spawned props are NOT part
of the official acoustic octree. PierHarbor ships with the official
``PierHarbor-HoveringImagingSonar`` scenario whose spawn pose aims the sonar
at stock pier structures — static geometry that IS in the octree. This
script verifies that on this machine, maps the local bathymetry, and gathers
the first sonar dataset for detector development.

Outputs (outputs/pierharbor_recon_<ts>/):
- bathymetry grid (npz + png) around the candidate site;
- sonar frames at aimed/offset/away poses (npz + rendered png);
- RGB camera snapshots at each pose;
- detector dry-run results per pose;
- summary.json with the proposed mission anchor.
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
AGENT = "recon"
# Official sonar-demo pose from PierHarbor-HoveringImagingSonar.json:
OFFICIAL_POSE = ([486.0, -632.0, -12.0], 180.0)  # (xyz, yaw deg): sonar aims -x

SONAR_CFG = {
    "RangeMin": 1.0,
    "RangeMax": 40.0,
    "RangeBins": 512,
    "AzimuthBins": 256,
    "Azimuth": 120.0,
    "Elevation": 20.0,
    "InitOctreeRange": 50.0,
    "ShowWarning": False,
}

POSES = [
    ("aimed_official", [486.0, -632.0, -12.0], 180.0),
    ("aimed_near", [478.0, -632.0, -12.0], 180.0),
    ("aimed_far", [498.0, -632.0, -12.0], 180.0),
    ("away_openwater", [486.0, -632.0, -12.0], 0.0),
]
SETTLE, FRAMES, KEEP = 70, 10, 6


def scenario() -> dict:
    return {
        "name": "pierharbor_recon",
        "package_name": "Ocean",
        "world": WORLD,
        "main_agent": AGENT,
        "ticks_per_sec": 30,
        "frames_per_sec": False,
        "octree_min": 0.05,
        "octree_max": 5.0,
        "agents": [{
            "agent_name": AGENT,
            "agent_type": "BlueROV2",
            "sensors": [
                {"sensor_type": "PoseSensor", "socket": "IMUSocket"},
                {"sensor_type": "LocationSensor", "socket": "IMUSocket"},
                {"sensor_type": "RangeFinderSensor", "socket": "SonarSocket",
                 "configuration": {"LaserCount": 4, "LaserAngle": -90,
                                   "LaserMaxDistance": 80}},
                {"sensor_type": "ImagingSonar", "socket": "SonarSocket",
                 "configuration": dict(SONAR_CFG)},
                {"sensor_type": "RGBCamera", "socket": "CameraSocket",
                 "configuration": {"CaptureWidth": 640, "CaptureHeight": 360}},
            ],
            "control_scheme": 1,
            "location": list(OFFICIAL_POSE[0]),
            "rotation": [0.0, 0.0, OFFICIAL_POSE[1]],
        }],
        "window_width": 900,
        "window_height": 506,
    }


def render_sonar(arr: np.ndarray, path: Path, title: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 5), constrained_layout=True)
    img = ax.imshow(np.log1p(arr), origin="lower", aspect="auto", cmap="inferno",
                    extent=[-SONAR_CFG["Azimuth"] / 2, SONAR_CFG["Azimuth"] / 2,
                            SONAR_CFG["RangeMin"], SONAR_CFG["RangeMax"]])
    ax.set_xlabel("Azimuth (deg)")
    ax.set_ylabel("Range (m)")
    ax.set_title(title)
    fig.colorbar(img, ax=ax, label="log(1+intensity)")
    fig.savefig(path, dpi=130)
    plt.close(fig)


def save_rgb(pixels: np.ndarray, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rgb = np.asarray(pixels)[:, :, :3][:, :, ::-1]  # BGRA -> RGB
    plt.imsave(path, rgb.astype(np.uint8))


def main() -> int:
    import holoocean

    from brinewatch.perception.sonar_diffuser_detector import SonarDiffuserDetector
    from brinewatch.sensors.sonar_types import SonarFrame
    from brinewatch.simulation.octree_cache import clear_world_octrees

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out = REPO_ROOT / "outputs" / f"pierharbor_recon_{stamp}"
    out.mkdir(parents=True, exist_ok=True)

    # One-time clean build at our standardized octree resolution (0.05/5.0);
    # the cache is then kept for all future PierHarbor runs.
    clear_world_octrees(WORLD)

    env = holoocean.make(scenario_cfg=scenario(), show_viewport=True, verbose=False)
    agent = env.agents[AGENT]
    detector = SonarDiffuserDetector()

    def hold(pose_xyz, yaw_deg, ticks):
        cmd = np.array([*pose_xyz, 0.0, 0.0, yaw_deg], dtype=np.float64)
        agent.teleport(list(pose_xyz), [0.0, 0.0, yaw_deg])
        state = None
        for _ in range(ticks):
            env.act(AGENT, cmd)
            state = env.tick()
        return state

    # ---------------- bathymetry scan around the candidate site ----------- #
    print("[recon] bathymetry scan ...")
    cx, cy = 470.0, -632.0
    xs = np.arange(cx - 40, cx + 41, 20.0)
    ys = np.arange(cy - 40, cy + 41, 20.0)
    bathy = np.full((len(ys), len(xs)), np.nan)
    for i, y in enumerate(ys):
        for j, x in enumerate(xs):
            state = hold([float(x), float(y), -8.0], 180.0, 12)
            rf = np.asarray(state["RangeFinderSensor"], dtype=float)
            valid = rf[rf > 0]
            if valid.size:
                z = float(np.asarray(state["LocationSensor"], dtype=float)[2])
                bathy[i, j] = z - float(valid.min())
    np.savez(out / "bathymetry.npz", xs=xs, ys=ys, bed_z=bathy)
    print(f"[recon] bed z: min={np.nanmin(bathy):.1f} max={np.nanmax(bathy):.1f}")

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6, 5), constrained_layout=True)
    im = ax.pcolormesh(xs, ys, bathy, cmap="viridis")
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_title("PierHarbor local seabed z (RangeFinder)")
    fig.colorbar(im, ax=ax, label="bed z (m)")
    fig.savefig(out / "bathymetry.png", dpi=130)
    plt.close(fig)

    # ---------------- sonar + camera at each pose ------------------------- #
    results = []
    for name, xyz, yaw in POSES:
        state = hold(xyz, yaw, SETTLE)
        frames = []
        for _ in range(FRAMES):
            cmd = np.array([*xyz, 0.0, 0.0, yaw], dtype=np.float64)
            env.act(AGENT, cmd)
            state = env.tick()
            if "ImagingSonar" in state:
                frames.append(np.asarray(state["ImagingSonar"], dtype=np.float32))
        frames = np.stack(frames[-KEEP:])
        np.save(out / f"sonar_{name}.npy", frames)
        mean = frames.mean(axis=0)
        render_sonar(mean, out / f"sonar_{name}.png", f"ImagingSonar — {name}")
        if "RGBCamera" in state:
            save_rgb(state["RGBCamera"], out / f"camera_{name}.png")

        loc = np.asarray(state["LocationSensor"], dtype=float)
        pose = np.asarray(state["PoseSensor"], dtype=float)
        yaw_rad = float(np.arctan2(pose[1, 0], pose[0, 0]))
        frame = SonarFrame(
            t=float(state["t"]), image=mean,
            range_min_m=SONAR_CFG["RangeMin"], range_max_m=SONAR_CFG["RangeMax"],
            azimuth_fov_deg=SONAR_CFG["Azimuth"], elevation_fov_deg=SONAR_CFG["Elevation"],
            vehicle_xyz=(float(loc[0]), float(loc[1]), float(loc[2])),
            vehicle_rpy=(0.0, 0.0, yaw_rad),
        )
        contacts = detector.detect(frame)
        results.append({
            "pose": name, "xyz": list(map(float, xyz)), "yaw_deg": yaw,
            "frame_max": float(mean.max()), "frame_mean": float(mean.mean()),
            "n_contacts": len(contacts),
            "contacts": [{"range_m": round(c.range_m, 2),
                          "bearing_deg": round(np.degrees(c.bearing_rad), 1),
                          "strength": round(c.strength, 2),
                          "area": c.area_bins,
                          "est_world": [round(frame.vehicle_xyz[0] + c.range_m * np.cos(yaw_rad + c.bearing_rad), 1),
                                        round(frame.vehicle_xyz[1] + c.range_m * np.sin(yaw_rad + c.bearing_rad), 1)]}
                         for c in contacts],
        })
        print(f"[recon] {name}: max={mean.max():.3f} contacts={len(contacts)}")

    (out / "summary.json").write_text(json.dumps(
        {"world": WORLD, "sonar_cfg": SONAR_CFG, "poses": results}, indent=2),
        encoding="utf-8")
    print(f"[recon] DONE -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

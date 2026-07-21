"""Localization v2 on the actual outfall: pose-matched background subtraction.

Real-survey analogue: a pre-installation baseline pass and post-installation
inspection passes over the same waypoints; change detection isolates the new
structure from native clutter exactly (deterministic sonar, pose-pinned).

Modes (fresh engine session per invocation):

  --mode background --out DIR      no structure; capture ALL orbit poses used
                                   by every acquisition (radii x bearings)
  --mode orbit --radius R --phase P --seed S --out DIR
                                   outfall spawned (SpawnAsset); one orbit
                                   acquisition at radius R with bearing phase
                                   offset P deg; sensor noise seeded with S
                                   (AddSigma/MultSigma > 0: each acquisition
                                   is a distinct noise realization)
  --analyze --out DIR              offline: tuning on the acquisition tagged
                                   'tune', validation on the others; per-run
                                   estimates, errors, fallback; metrics JSON

No ground truth reaches the locator; the true diffuser centre is used only
for scoring at analysis time.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

AGENT = "rov"
SITE = (30.0, 0.0)
YAW_DEG = 0.0
from brinewatch.simulation.outfall_scene import OutfallSceneConfig  # noqa: E402
L_DIFF = OutfallSceneConfig().diffuser_length_m   # actual generated length (19.6 m)
SONAR = {"rmin": 1.0, "rmax": 40.0, "az": 120.0, "elev": 20.0,
         "range_bins": 512, "az_bins": 256}
N_POSES = 16
RADII = (18.0, 22.0)   # orbit radii used by acquisitions
PHASES = (0.0, 11.25)  # bearing phase offsets (deg)


def orbit_poses(radius: float, phase_deg: float, bed_z: float):
    cx = SITE[0] + math.cos(math.radians(YAW_DEG)) * L_DIFF / 2.0
    cy = SITE[1] + math.sin(math.radians(YAW_DEG)) * L_DIFF / 2.0
    for k in range(N_POSES):
        b = math.radians(phase_deg) + 2 * math.pi * k / N_POSES
        px, py = cx + radius * math.cos(b), cy + radius * math.sin(b)
        yaw = math.degrees(math.atan2(cy - py, cx - px))
        yield (f"r{int(radius):02d}_p{int(round(phase_deg * 100)):04d}_k{k:02d}",
               px, py, bed_z + 3.0, yaw)


def attach(noise_seed=None):
    from brinewatch.simulation.custom_engine import (
        activate_fork_client, resolve_custom_engine,
    )
    engine = resolve_custom_engine()
    holoocean = activate_fork_client(engine)
    sigma = 0.05 if noise_seed is not None else 0.0
    scenario = {
        "name": "loc_v2", "world": engine.level, "package_name": "Ocean",
        "main_agent": AGENT, "ticks_per_sec": 30, "frames_per_sec": False,
        "agents": [{
            "agent_name": AGENT, "agent_type": "BlueROV2",
            "sensors": [
                {"sensor_type": "LocationSensor", "socket": "IMUSocket"},
                {"sensor_type": "RangeFinderSensor", "socket": "SonarSocket",
                 "configuration": {"LaserCount": 4, "LaserAngle": -90,
                                   "LaserMaxDistance": 120}},
                {"sensor_type": "ImagingSonar", "socket": "SonarSocket",
                 "configuration": {
                     "RangeBins": SONAR["range_bins"],
                     "AzimuthBins": SONAR["az_bins"],
                     "RangeMin": SONAR["rmin"], "RangeMax": SONAR["rmax"],
                     "InitOctreeRange": 50.0, "Elevation": SONAR["elev"],
                     "Azimuth": SONAR["az"], "TicksPerCapture": 30,
                     "AddSigma": sigma, "MultSigma": sigma,
                     "ViewOctree": -1}},
            ],
            "control_scheme": 1,
            "location": [SITE[0] - 30.0, SITE[1] - 30.0, -40.0],
            "rotation": [0.0, 0.0, 45.0],
        }],
    }
    env = holoocean.make(scenario_cfg=scenario, start_world=False,
                         show_viewport=True, verbose=False)
    env.reset()
    return env, holoocean


def capture_run(env, agent, poses, out, tag):
    frames, meta = {}, {}
    for key, px, py, pz, yaw in poses:
        cmd = np.array([px, py, pz, 0.0, 0.0, yaw], dtype=np.float64)
        state, img = None, None
        for _ in range(8):
            agent.teleport([px, py, pz], [0.0, 0.0, yaw])
            env.act(AGENT, cmd)
            state = env.tick()
        for _ in range(240):
            agent.teleport([px, py, pz], [0.0, 0.0, yaw])
            env.act(AGENT, cmd)
            state = env.tick()
            if "ImagingSonar" in state:
                img = np.asarray(state["ImagingSonar"], dtype=float).copy()
                break
        if img is None:
            print(f"[{tag}] WARNING no frame at {key}")
            continue
        loc = np.asarray(state["LocationSensor"], dtype=float)
        frames[key] = img
        meta[key] = {"commanded": [px, py, pz, yaw],
                     "actual_xyz": [round(float(v), 4) for v in loc],
                     "yaw_rad": math.radians(yaw)}
        print(f"[{tag}] {key}")
    np.savez_compressed(out / f"frames_{tag}.npz", **frames)
    (out / f"meta_{tag}.json").write_text(json.dumps(meta, indent=2),
                                          encoding="utf-8")
    return len(frames)


def probe_bed(env, agent):
    cmd = np.array([SITE[0], SITE[1], -40.0, 0.0, 0.0, 0.0], dtype=np.float64)
    state = None
    for _ in range(15):
        agent.teleport([SITE[0], SITE[1], -40.0], [0.0, 0.0, 0.0])
        env.act(AGENT, cmd)
        state = env.tick()
    rf = np.asarray(state["RangeFinderSensor"], dtype=float)
    loc = np.asarray(state["LocationSensor"], dtype=float)
    return float(loc[2]) - float(rf[rf > 0].min())


def build_outfall(env, holoocean, bed_z):
    from brinewatch.simulation.custom_engine import make_asset_spawner
    from brinewatch.simulation.outfall_scene import (
        OutfallSceneBuilder, OutfallSceneConfig,
    )
    from brinewatch.utils.config import OutfallConfig
    from brinewatch.utils.terrain import TerrainMap

    xs = np.linspace(SITE[0] - 60, SITE[0] + 60, 13)
    ys = np.linspace(SITE[1] - 60, SITE[1] + 60, 13)
    builder = OutfallSceneBuilder(
        env=env, agent_name=AGENT,
        outfall=OutfallConfig(x=SITE[0], y=SITE[1], axis_deg=YAW_DEG,
                              n_ports=6, port_spacing_m=3.2),
        scene=OutfallSceneConfig(structure_yaw_deg=YAW_DEG, scatter_rocks=0),
        terrain=TerrainMap(xs, ys, np.full((13, 13), bed_z)),
        spawn_fn=make_asset_spawner(env, holoocean))
    builder.build()
    env.tick()
    time.sleep(1.0)
    return builder


def run_background(args) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    env, _ = attach()
    agent = env.agents[AGENT]
    bed_z = probe_bed(env, agent)
    print(f"[background] bed {bed_z:.2f}")
    poses = []
    for r in RADII:
        for p in PHASES:
            poses.extend(orbit_poses(r, p, bed_z))
    n = capture_run(env, agent, poses, out, "background")
    (out / "site.json").write_text(json.dumps(
        {"bed_z": bed_z, "site": SITE, "yaw_deg": YAW_DEG,
         "true_diffuser_centre": [SITE[0] + L_DIFF / 2.0, SITE[1]],
         "radii": RADII, "phases": PHASES, "n_poses": N_POSES}),
        encoding="utf-8")
    print(f"[background] DONE {n} poses")
    return 0


def run_orbit(args) -> int:
    out = Path(args.out)
    site = json.loads((out / "site.json").read_text(encoding="utf-8"))
    env, holoocean = attach(noise_seed=args.seed)
    agent = env.agents[AGENT]
    bed_z = probe_bed(env, agent)
    build_outfall(env, holoocean, bed_z)
    tag = f"acq_r{int(args.radius):02d}_p{int(round(args.phase * 100)):04d}_s{args.seed}"
    n = capture_run(env, agent,
                    orbit_poses(args.radius, args.phase, site["bed_z"]),
                    out, tag)
    print(f"[orbit] DONE {tag}: {n} poses")
    return 0


# --------------------------------------------------------------------------- #
def analyze(args) -> int:
    from brinewatch.perception.sonar_diffuser_detector import (
        DetectorConfig, SonarDiffuserDetector,
    )
    from brinewatch.sensors.sonar_types import SonarFrame

    out = Path(args.out)
    site = json.loads((out / "site.json").read_text(encoding="utf-8"))
    cx, cy = site["true_diffuser_centre"]
    bg = dict(np.load(out / "frames_background.npz"))
    acq_files = sorted(out.glob("frames_acq_*.npz"))
    if not acq_files:
        print("[analyze] no acquisitions")
        return 1

    det = SonarDiffuserDetector(DetectorConfig(min_range_m=6.0,
                                               z_threshold=3.5,
                                               min_area_bins=8))

    def frame_of(img, meta):
        return SonarFrame(t=0.0, image=np.asarray(img, dtype=np.float32),
                          range_min_m=SONAR["rmin"], range_max_m=SONAR["rmax"],
                          azimuth_fov_deg=SONAR["az"],
                          elevation_fov_deg=SONAR["elev"],
                          vehicle_xyz=tuple(meta["actual_xyz"][:3]),
                          vehicle_rpy=(0.0, 0.0, meta["yaw_rad"]))

    results = {}
    for f in acq_files:
        tag = f.stem.replace("frames_", "")
        frames = dict(np.load(f))
        meta = json.loads((out / f"meta_{tag}.json").read_text(
            encoding="utf-8"))
        ests = []
        n_contacts = 0
        headings = []
        for key, img in frames.items():
            if key not in bg or key not in meta:
                continue
            residual = np.clip(img - bg[key], 0.0, None)
            fr = frame_of(residual, meta[key])
            for c in det.detect(fr):
                n_contacts += 1
                # world projection of the contact centroid
                brg = fr.vehicle_rpy[2] + float(
                    fr.bearing_of_col(c.centroid_col))
                ex = fr.vehicle_xyz[0] + c.range_m * math.cos(brg)
                ey = fr.vehicle_xyz[1] + c.range_m * math.sin(brg)
                ests.append((ex, ey, fr.vehicle_rpy[2], c.strength))
        entry = {"n_frames": len(frames), "n_contacts": n_contacts}
        if len(ests) >= 5:
            pts = np.asarray([(e[0], e[1]) for e in ests])
            # weighted mode cluster: densest 5 m neighbourhood
            d2 = ((pts[:, None, :] - pts[None, :, :]) ** 2).sum(-1)
            counts = (d2 < 25.0).sum(1)
            core = pts[d2[int(np.argmax(counts))] < 25.0]
            est = core.mean(0)
            # aspect diversity of the core cluster
            core_idx = np.nonzero(d2[int(np.argmax(counts))] < 25.0)[0]
            hs = [ests[i][2] for i in core_idx]
            aspect = math.degrees(max(hs) - min(hs)) if hs else 0.0
            err = float(math.hypot(est[0] - cx, est[1] - cy))
            # distance to the structure axis segment (site -> site+L along x)
            t = max(SITE[0], min(SITE[0] + L_DIFF, est[0]))
            d_axis = float(math.hypot(est[0] - t, est[1] - SITE[1]))
            entry.update({"estimate": [round(float(est[0]), 2),
                                       round(float(est[1]), 2)],
                          "core_size": int(len(core)),
                          "aspect_span_deg": round(aspect, 1),
                          "error_to_centre_m": round(err, 2),
                          "dist_to_axis_m": round(d_axis, 2),
                          "fallback": False})
        else:
            entry.update({"estimate": None, "fallback": True})
        results[tag] = entry
        print(f"[analyze] {tag}: {entry}")

    errs = [v["error_to_centre_m"] for v in results.values()
            if not v.get("fallback")]
    summary = {
        "n_acquisitions": len(results),
        "success": len(errs),
        "fallback_rate": round(1.0 - len(errs) / max(len(results), 1), 3),
        "median_error_m": round(float(np.median(errs)), 2) if errs else None,
        "mean_error_m": round(float(np.mean(errs)), 2) if errs else None,
        "p95_error_m": round(float(np.percentile(errs, 95)), 2) if errs else None,
        "max_error_m": round(float(np.max(errs)), 2) if errs else None,
        "note": ("independent engine sessions per acquisition; pose-matched "
                 "background subtraction removes native clutter; true centre "
                 "used only here for scoring"),
    }
    (out / "analysis.json").write_text(
        json.dumps({"summary": summary, "runs": results}, indent=2),
        encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mode", choices=["background", "orbit"])
    ap.add_argument("--analyze", action="store_true")
    ap.add_argument("--out", required=True)
    ap.add_argument("--radius", type=float, default=18.0)
    ap.add_argument("--phase", type=float, default=0.0)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    if args.analyze:
        return analyze(args)
    if args.mode == "background":
        return run_background(args)
    if args.mode == "orbit":
        return run_orbit(args)
    print("need --mode or --analyze")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Localization study on the ACTUAL outfall (custom engine).

One engine session: build the outfall via SpawnAsset, fly a 16-pose orbit
recording deterministic-noise-free sonar frames + synchronized poses, then run
the FULL sonar localization stack (detector + mode-cluster consensus locator)
OFFLINE over a sweep of chart priors (4 directions x 3 offsets). No ground
truth reaches the locator: the true structure position is used only for
scoring. Outputs: frames npz + study.json (per-prior estimate, error,
n_detections, fallback flag).

Requires a FRESH fork engine session (scripts/launch_custom_engine.py).
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from brinewatch.simulation.custom_engine import (  # noqa: E402
    activate_fork_client,
    make_asset_spawner,
    resolve_custom_engine,
)

AGENT = "rov"
SITE = (30.0, 0.0)
YAW_DEG = 0.0
SONAR = {"rmin": 1.0, "rmax": 40.0, "az": 120.0, "elev": 20.0}
N_POSES = 16
ORBIT_R = 20.0


def main() -> int:
    engine = resolve_custom_engine()
    holoocean = activate_fork_client(engine)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = REPO / "outputs" / f"custom_localization_{stamp}"
    out.mkdir(parents=True, exist_ok=True)

    scenario = {
        "name": "custom_loc", "world": engine.level, "package_name": "Ocean",
        "main_agent": AGENT, "ticks_per_sec": 30, "frames_per_sec": False,
        "agents": [{
            "agent_name": AGENT, "agent_type": "BlueROV2",
            "sensors": [
                {"sensor_type": "LocationSensor", "socket": "IMUSocket"},
                {"sensor_type": "RotationSensor", "socket": "IMUSocket"},
                {"sensor_type": "RangeFinderSensor", "socket": "SonarSocket",
                 "configuration": {"LaserCount": 4, "LaserAngle": -90,
                                   "LaserMaxDistance": 120}},
                {"sensor_type": "ImagingSonar", "socket": "SonarSocket",
                 "configuration": {
                     "RangeBins": 512, "AzimuthBins": 256,
                     "RangeMin": SONAR["rmin"], "RangeMax": SONAR["rmax"],
                     "InitOctreeRange": 50.0, "Elevation": SONAR["elev"],
                     "Azimuth": SONAR["az"], "TicksPerCapture": 30,
                     "AddSigma": 0.0, "MultSigma": 0.0, "ViewOctree": -1,
                 }},
            ],
            "control_scheme": 1,
            "location": [SITE[0] - 30.0, SITE[1] - 30.0, -40.0],
            "rotation": [0.0, 0.0, 45.0],
        }],
    }
    env = holoocean.make(scenario_cfg=scenario, start_world=False,
                         show_viewport=True, verbose=False)
    env.reset()
    agent = env.agents[AGENT]
    print("[loc] attached")

    def hold(pos, yaw, ticks=10, grab_sonar=False):
        cmd = np.array([*pos, 0.0, 0.0, yaw], dtype=np.float64)
        state, frame = None, None
        n = 240 if grab_sonar else ticks
        for _ in range(n):
            agent.teleport(list(pos), [0.0, 0.0, yaw])
            env.act(AGENT, cmd)
            state = env.tick()
            if grab_sonar and "ImagingSonar" in state:
                frame = np.asarray(state["ImagingSonar"], dtype=float).copy()
                break
        return state, frame

    # bed depth
    state, _ = hold([SITE[0], SITE[1], -40.0], 0.0, ticks=15)
    rf = np.asarray(state["RangeFinderSensor"], dtype=float)
    loc = np.asarray(state["LocationSensor"], dtype=float)
    bed_z = float(loc[2]) - float(rf[rf > 0].min())
    print(f"[loc] bed z = {bed_z:.2f}")

    # build the outfall (SpawnAsset)
    from brinewatch.simulation.outfall_scene import (
        OutfallSceneBuilder, OutfallSceneConfig,
    )
    from brinewatch.utils.config import OutfallConfig
    from brinewatch.utils.terrain import TerrainMap

    xs = np.linspace(SITE[0] - 60, SITE[0] + 60, 13)
    ys = np.linspace(SITE[1] - 60, SITE[1] + 60, 13)
    terrain = TerrainMap(xs, ys, np.full((13, 13), bed_z))
    builder = OutfallSceneBuilder(
        env=env, agent_name=AGENT,
        outfall=OutfallConfig(x=SITE[0], y=SITE[1], axis_deg=YAW_DEG,
                              n_ports=6, port_spacing_m=3.2),
        scene=OutfallSceneConfig(structure_yaw_deg=YAW_DEG, scatter_rocks=0),
        terrain=terrain, spawn_fn=make_asset_spawner(env, holoocean))
    builder.build()
    env.tick()

    L = builder.scene.diffuser_length_m
    cx = SITE[0] + math.cos(math.radians(YAW_DEG)) * L / 2.0
    cy = SITE[1] + math.sin(math.radians(YAW_DEG)) * L / 2.0
    true_xy = (cx, cy)
    z_fly = bed_z + 3.0

    # orbit + record
    records = []
    for k in range(N_POSES):
        b = 2 * math.pi * k / N_POSES
        px, py = cx + ORBIT_R * math.cos(b), cy + ORBIT_R * math.sin(b)
        yaw = math.degrees(math.atan2(cy - py, cx - px))
        hold([px, py, z_fly], yaw, ticks=8)
        state, img = hold([px, py, z_fly], yaw, grab_sonar=True)
        if img is None:
            print(f"[loc] WARNING no frame at pose {k}")
            continue
        lo = np.asarray(state["LocationSensor"], dtype=float)
        records.append({"image": img, "xyz": lo.tolist(),
                        "yaw_rad": math.radians(yaw)})
        print(f"[loc] pose {k + 1}/{N_POSES} recorded")

    np.savez_compressed(
        out / "orbit_frames.npz",
        **{f"img_{i:02d}": r["image"] for i, r in enumerate(records)})
    (out / "orbit_poses.json").write_text(json.dumps(
        [{"xyz": r["xyz"], "yaw_rad": r["yaw_rad"]} for r in records],
        indent=2), encoding="utf-8")

    # ---- offline localization sweep -------------------------------------- #
    from brinewatch.perception.sonar_diffuser_detector import DetectorConfig
    from brinewatch.perception.sonar_localizer import (
        SonarDiffuserLocator, SonarLocalizerConfig,
    )
    from brinewatch.sensors.sonar_types import SonarFrame

    def frames():
        for i, r in enumerate(records):
            yield SonarFrame(
                t=float(i), image=np.asarray(r["image"], dtype=np.float32),
                range_min_m=SONAR["rmin"], range_max_m=SONAR["rmax"],
                azimuth_fov_deg=SONAR["az"], elevation_fov_deg=SONAR["elev"],
                vehicle_xyz=tuple(r["xyz"]),
                vehicle_rpy=(0.0, 0.0, r["yaw_rad"]))

    study = {"true_xy": true_xy, "bed_z": bed_z, "n_frames": len(records),
             "orbit_radius_m": ORBIT_R, "priors": []}
    for d_bear in (0.0, 90.0, 180.0, 270.0):
        for d_off in (10.0, 18.0, 26.0):
            pr = (cx + d_off * math.cos(math.radians(d_bear)),
                  cy + d_off * math.sin(math.radians(d_bear)))
            locator = SonarDiffuserLocator(SonarLocalizerConfig(
                detector=DetectorConfig(min_range_m=8.0),
                min_strength=6.0, min_hits_for_consensus=10,
                prior_xy=pr, prior_gate_m=30.0))
            for fr in frames():
                locator.update(fr)
            est = locator.consensus
            err = (math.hypot(est[0] - cx, est[1] - cy)
                   if est is not None else None)
            study["priors"].append({
                "prior_offset_m": d_off, "prior_bearing_deg": d_bear,
                "prior_error_m": round(math.hypot(pr[0] - cx, pr[1] - cy), 2),
                "estimate": [round(v, 2) for v in est[:2]] if est is not None else None,
                "error_m": round(err, 2) if err is not None else None,
                "contacts_seen": locator.contacts_seen,
            })
            tag = f"prior {d_bear:>3.0f}deg/{d_off:>2.0f}m"
            print(f"[loc] {tag}: est err = "
                  f"{'%.2f m' % err if err is not None else 'NO CONSENSUS'}")

    (out / "study.json").write_text(json.dumps(study, indent=2),
                                    encoding="utf-8")
    errs = [p["error_m"] for p in study["priors"] if p["error_m"] is not None]
    ok = len(errs)
    print(f"[loc] DONE -> {out}")
    print(f"[loc] consensus rate {ok}/{len(study['priors'])}; "
          f"median err {np.median(errs):.2f} m" if ok else "[loc] NO consensus")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

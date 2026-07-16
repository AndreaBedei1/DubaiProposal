"""A/B/C sonar-visibility experiment on the ACTUAL generated outfall (custom engine).

Conditions, all in ONE custom-engine session (fork, runtime octree rebuild):

  A  no structure                       -> baseline frames
  B  outfall via legacy SpawnProp path  -> blueprint props; NOT static geometry.
     Expectation: frames ~= A (acoustically invisible), like the official engine.
  C  outfall via SpawnAsset path        -> static meshes, octree marked dirty and
     rebuilt by the sonar tick. Expectation: strong, structured returns.
  D  ClearSpawned                       -> frames return to ~= A (rebuild on removal).

Captures at multiple aspects/ranges around the structure; quantitative per-pose
frame differences + detector contacts; everything saved under outputs/.

Run with the fork engine already up (scripts/launch_custom_engine.py) and
HOLOOCEAN_CUSTOM_ENGINE_PATH set. Fresh process required.
"""
from __future__ import annotations

import json
import math
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from brinewatch.simulation.custom_engine import (  # noqa: E402
    activate_fork_client,
    clear_spawned,
    make_asset_spawner,
    resolve_custom_engine,
)

AGENT = "rov"
SITE = (30.0, 0.0)          # structure origin (diffuser start) in ExampleLevel
YAW_DEG = 0.0               # structure axis: +x
SONAR_RANGE = (1.0, 40.0)
POSES = [                    # (bearing from centre deg, range m)
    (0.0, 18.0), (90.0, 18.0), (180.0, 18.0), (270.0, 18.0),
    (45.0, 28.0), (225.0, 28.0),
]


def main() -> int:
    engine = resolve_custom_engine()
    holoocean = activate_fork_client(engine)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = REPO / "outputs" / f"custom_sonar_abc_{stamp}"
    out.mkdir(parents=True, exist_ok=True)

    scenario = {
        "name": "custom_abc",
        "world": engine.level,
        "package_name": "Ocean",
        "main_agent": AGENT,
        "ticks_per_sec": 30,
        "frames_per_sec": False,   # attach-mode make() blocks on input() otherwise
        "agents": [{
            "agent_name": AGENT,
            "agent_type": "BlueROV2",
            "sensors": [
                {"sensor_type": "LocationSensor", "socket": "IMUSocket"},
                {"sensor_type": "RangeFinderSensor", "socket": "SonarSocket",
                 "configuration": {"LaserCount": 4, "LaserAngle": -90,
                                   "LaserMaxDistance": 120}},
                {"sensor_type": "ImagingSonar", "socket": "SonarSocket",
                 "configuration": {
                     "RangeBins": 512, "AzimuthBins": 256,
                     "RangeMin": SONAR_RANGE[0], "RangeMax": SONAR_RANGE[1],
                     "InitOctreeRange": 50.0,
                     "Elevation": 20.0, "Azimuth": 120.0,
                     "TicksPerCapture": 30,
                     "AddSigma": 0.0, "MultSigma": 0.0,  # deterministic frames
                     "ViewOctree": -1,
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
    print("[abc] attached; agent up")

    # ---- probe the seabed once (bed z under the site) -------------------- #
    def hold(pos, yaw, pitch=0.0, ticks=20, want=None):
        cmd = np.array([*pos, 0.0, pitch, yaw], dtype=np.float64)
        state = None
        got = None
        for _ in range(ticks):
            agent.teleport(list(pos), [0.0, pitch, yaw])
            env.act(AGENT, cmd)
            state = env.tick()
            if want and want in state:
                got = np.asarray(state[want], dtype=float).copy()
        return state, got

    state, _ = hold([SITE[0], SITE[1], -40.0], 0.0, ticks=15)
    rf = np.asarray(state["RangeFinderSensor"], dtype=float)
    valid = rf[rf > 0]
    if valid.size == 0:
        state, _ = hold([SITE[0], SITE[1], -20.0], 0.0, ticks=15)
        rf = np.asarray(state["RangeFinderSensor"], dtype=float)
        valid = rf[rf > 0]
    loc = np.asarray(state["LocationSensor"], dtype=float)
    if valid.size == 0:
        print("[abc] FATAL: no seabed return under the site")
        return 1
    bed_z = float(loc[2]) - float(valid.min())
    print(f"[abc] seabed at site: z = {bed_z:.2f}")

    # ---- build the ACTUAL outfall geometry (same builder as the visuals) - #
    from brinewatch.simulation.outfall_scene import (
        OutfallSceneBuilder, OutfallSceneConfig,
    )
    from brinewatch.utils.config import OutfallConfig
    from brinewatch.utils.terrain import TerrainMap

    # flat synthetic terrain at the probed depth (ExampleLevel bed is flat
    # around the site; the experiment needs placement, not cm accuracy)
    xs = np.linspace(SITE[0] - 60, SITE[0] + 60, 13)
    ys = np.linspace(SITE[1] - 60, SITE[1] + 60, 13)
    zz = np.full((13, 13), bed_z)
    terrain = TerrainMap(xs, ys, zz)

    outfall_cfg = OutfallConfig(x=SITE[0], y=SITE[1], axis_deg=YAW_DEG,
                                n_ports=6, port_spacing_m=3.2)
    scene_cfg = OutfallSceneConfig(structure_yaw_deg=YAW_DEG, scatter_rocks=0)

    centre_s = (scene_cfg.diffuser_length_m / 2.0)
    cx = SITE[0] + math.cos(math.radians(YAW_DEG)) * centre_s
    cy = SITE[1] + math.sin(math.radians(YAW_DEG)) * centre_s
    z_fly = bed_z + 3.0

    def capture_all(tag):
        frames = {}
        for bearing, rng in POSES:
            b = math.radians(bearing)
            px, py = cx + rng * math.cos(b), cy + rng * math.sin(b)
            yaw = math.degrees(math.atan2(cy - py, cx - px))
            # settle, then keep ticking until 2 fresh sonar frames arrive
            hold([px, py, z_fly], yaw, ticks=10)
            got = []
            cmd = np.array([px, py, z_fly, 0.0, 0.0, yaw], dtype=np.float64)
            for _ in range(240):
                agent.teleport([px, py, z_fly], [0.0, 0.0, yaw])
                env.act(AGENT, cmd)
                st = env.tick()
                if "ImagingSonar" in st:
                    got.append(np.asarray(st["ImagingSonar"], dtype=float).copy())
                    if len(got) >= 2:
                        break
            if not got:
                print(f"[abc] WARNING: no sonar frame at pose {bearing}/{rng}")
                continue
            frames[f"b{int(bearing):03d}_r{int(rng):02d}"] = got[-1]
        np.savez_compressed(out / f"frames_{tag}.npz", **frames)
        print(f"[abc] {tag}: captured {len(frames)}/{len(POSES)} poses")
        return frames

    def spawn_prop_structure():
        builder = OutfallSceneBuilder(env=env, agent_name=AGENT,
                                      outfall=outfall_cfg, scene=scene_cfg,
                                      terrain=terrain)
        builder.build()
        return builder

    # ---------------- A: baseline ----------------------------------------- #
    frames_a = capture_all("A_no_structure")

    # ---------------- B: legacy SpawnProp (blueprint props) --------------- #
    try:
        spawn_prop_structure()
        env.tick()
        b_ok = True
    except Exception as exc:  # fork may not ship the SpawnProp blueprint path
        print(f"[abc] B-phase spawn_prop unavailable in fork client: {exc}")
        b_ok = False
    frames_b = capture_all("B_spawn_prop") if b_ok else {}

    # ---------------- C: SpawnAsset (static meshes, octree rebuild) ------- #
    builder = OutfallSceneBuilder(env=env, agent_name=AGENT,
                                  outfall=outfall_cfg, scene=scene_cfg,
                                  terrain=terrain,
                                  spawn_fn=make_asset_spawner(env, holoocean))
    builder.build()
    builder.save_manifest(out / "scene_manifest.json")
    env.tick()
    time.sleep(1.0)  # let the engine consume the dirty flag on its next sonar tick
    frames_c = capture_all("C_spawn_asset")

    # ---------------- D: ClearSpawned ------------------------------------- #
    clear_spawned(env, holoocean)
    env.tick()
    time.sleep(1.0)
    frames_d = capture_all("D_cleared")

    # ---------------- metrics --------------------------------------------- #
    from brinewatch.perception.sonar_diffuser_detector import (
        DetectorConfig, SonarDiffuserDetector,
    )
    from brinewatch.sensors.sonar_types import SonarFrame

    det = SonarDiffuserDetector(DetectorConfig(min_range_m=4.0))

    def as_frame(image: np.ndarray) -> SonarFrame:
        return SonarFrame(t=0.0, image=np.asarray(image, dtype=np.float32),
                          range_min_m=SONAR_RANGE[0], range_max_m=SONAR_RANGE[1],
                          azimuth_fov_deg=120.0, elevation_fov_deg=20.0,
                          vehicle_xyz=(0.0, 0.0, 0.0),
                          vehicle_rpy=(0.0, 0.0, 0.0))

    report = {"site": SITE, "yaw_deg": YAW_DEG, "bed_z": bed_z, "poses": POSES,
              "phases": {}}
    for tag, frames in [("B_vs_A", frames_b), ("C_vs_A", frames_c),
                        ("D_vs_A", frames_d)]:
        per_pose = {}
        for key, ref in frames_a.items():
            if key not in frames:
                continue
            cur = frames[key]
            diff = float(np.abs(cur - ref).mean())
            identical = bool(np.array_equal(cur, ref))
            per_pose[key] = {"mean_abs_diff": round(diff, 6),
                             "bit_identical": identical}
        report["phases"][tag] = per_pose
        if per_pose:
            diffs = [v["mean_abs_diff"] for v in per_pose.values()]
            n_ident = sum(v["bit_identical"] for v in per_pose.values())
            print(f"[abc] {tag}: mean|diff| {np.mean(diffs):.6f} "
                  f"(bit-identical {n_ident}/{len(per_pose)})")

    # detector contacts on C frames (structure should be detected)
    contacts = {}
    for key, image in frames_c.items():
        try:
            hits = det.detect(as_frame(image))
            contacts[key] = [{"range_m": round(c.range_m, 1),
                              "bearing_deg": round(math.degrees(c.bearing_rad), 1),
                              "strength": round(c.strength, 1),
                              "area_bins": c.area_bins}
                             for c in hits]
        except Exception as exc:
            contacts[key] = f"detector error: {exc}"
    report["contacts_C"] = contacts

    (out / "report.json").write_text(json.dumps(report, indent=2),
                                     encoding="utf-8")
    print(f"[abc] DONE -> {out}")

    verdict_c = report["phases"].get("C_vs_A", {})
    changed = [k for k, v in verdict_c.items() if not v["bit_identical"]]
    print(f"[abc] C differs from A at {len(changed)}/{len(verdict_c)} poses")
    return 0 if changed else 1


if __name__ == "__main__":
    raise SystemExit(main())

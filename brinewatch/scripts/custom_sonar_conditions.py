"""Clean multi-session sonar visibility experiment (custom fork engine).

Each CONDITION runs in its own fresh engine session (no persistent-prop
contamination — supersedes the in-session A/B/C/D of validate_custom_sonar):

    A          no structure
    FULL       complete outfall (SpawnAsset)
    PIPE       approach pipeline + diffuser pipe only (no risers/nozzles)
    RISERS     risers + collars + nozzles only
    REMOVED    full outfall spawned, then ClearSpawned before capture

Usage (fresh engine per invocation, then one final offline analysis):

    python scripts/launch_custom_engine.py            # terminal 1, per run
    python scripts/custom_sonar_conditions.py --condition A    --out OUTDIR
    ... restart engine ...
    python scripts/custom_sonar_conditions.py --condition FULL --out OUTDIR
    ...
    python scripts/custom_sonar_conditions.py --analyze --out OUTDIR

Poses cover multiple bearings AND ranges (head-on/side/oblique/opposing x
near/moderate/far). Every capture records the ACTUAL vehicle pose so pose
repeatability across sessions is measured, not assumed. Expected echo
windows are derived from geometry + sensor pose at analysis time (committed
into the manifest), never hand-picked after inspection.
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
SONAR = {"rmin": 1.0, "rmax": 40.0, "az": 120.0, "elev": 20.0,
         "range_bins": 512, "az_bins": 256}
POSES = [  # (bearing deg from diffuser centre, range m)
    (0.0, 12.0), (0.0, 18.0), (0.0, 30.0),
    (90.0, 18.0), (180.0, 18.0), (270.0, 18.0),
    (45.0, 24.0), (225.0, 24.0),
]
CONDITIONS = ("A", "FULL", "PIPE", "RISERS", "REMOVED")


def component_filter(condition):
    if condition == "PIPE":
        keep = ("approach_pipe", "diffuser_pipe", "transition_collar",
                "approach_flange", "end_cap")
    elif condition == "RISERS":
        keep = ("riser", "nozzle")
    else:
        return None
    return lambda kind: any(kind.startswith(k) for k in keep)


def run_condition(args) -> int:
    from brinewatch.simulation.custom_engine import (
        activate_fork_client, clear_spawned, make_asset_spawner,
        resolve_custom_engine,
    )

    engine = resolve_custom_engine()
    holoocean = activate_fork_client(engine)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    scenario = {
        "name": f"sonar_cond_{args.condition}", "world": engine.level,
        "package_name": "Ocean", "main_agent": AGENT,
        "ticks_per_sec": 30, "frames_per_sec": False,
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
                     "AddSigma": 0.0, "MultSigma": 0.0, "ViewOctree": -1}},
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
    print(f"[cond {args.condition}] attached")

    def hold(pos, yaw, ticks=10, sonar_grab=False):
        cmd = np.array([*pos, 0.0, 0.0, yaw], dtype=np.float64)
        state, frame = None, None
        n = 240 if sonar_grab else ticks
        for _ in range(n):
            agent.teleport(list(pos), [0.0, 0.0, yaw])
            env.act(AGENT, cmd)
            state = env.tick()
            if sonar_grab and "ImagingSonar" in state:
                frame = np.asarray(state["ImagingSonar"], dtype=float).copy()
                break
        return state, frame

    state, _ = hold([SITE[0], SITE[1], -40.0], 0.0, ticks=15)
    rf = np.asarray(state["RangeFinderSensor"], dtype=float)
    loc = np.asarray(state["LocationSensor"], dtype=float)
    bed_z = float(loc[2]) - float(rf[rf > 0].min())
    print(f"[cond {args.condition}] bed z = {bed_z:.2f}")

    # ---- structure (per condition) ---------------------------------------- #
    from brinewatch.simulation.outfall_scene import (
        OutfallSceneBuilder, OutfallSceneConfig,
    )
    from brinewatch.utils.config import OutfallConfig
    from brinewatch.utils.terrain import TerrainMap

    manifest_path = out / f"scene_{args.condition}.json"
    if args.condition != "A":
        xs = np.linspace(SITE[0] - 60, SITE[0] + 60, 13)
        ys = np.linspace(SITE[1] - 60, SITE[1] + 60, 13)
        terrain = TerrainMap(xs, ys, np.full((13, 13), bed_z))
        spawn = make_asset_spawner(env, holoocean,
                                   label_prefix=f"cond_{args.condition}")
        keep = component_filter(args.condition)
        builder = OutfallSceneBuilder(
            env=env, agent_name=AGENT,
            outfall=OutfallConfig(x=SITE[0], y=SITE[1], axis_deg=YAW_DEG,
                                  n_ports=6, port_spacing_m=3.2),
            scene=OutfallSceneConfig(structure_yaw_deg=YAW_DEG,
                                     scatter_rocks=0),
            terrain=terrain, spawn_fn=spawn)
        if keep is not None:
            orig = builder._spawn

            def filtered(kind, *a, **kw):
                if keep(kind):
                    orig(kind, *a, **kw)
            builder._spawn = filtered
        builder.build()
        builder.save_manifest(manifest_path)
        env.tick()
        time.sleep(1.0)
        if args.condition == "REMOVED":
            clear_spawned(env, holoocean)
            env.tick()
            time.sleep(1.0)
        n_built = sum(1 for c in builder.components if c.ok)
        print(f"[cond {args.condition}] structure: {n_built} components"
              f"{' then ClearSpawned' if args.condition == 'REMOVED' else ''}")

    # ---- captures ---------------------------------------------------------- #
    L = 16.0
    cx = SITE[0] + math.cos(math.radians(YAW_DEG)) * L / 2.0
    cy = SITE[1] + math.sin(math.radians(YAW_DEG)) * L / 2.0
    z_fly = bed_z + 3.0
    frames, poses_actual = {}, {}
    for bearing, rng in POSES:
        b = math.radians(bearing)
        px, py = cx + rng * math.cos(b), cy + rng * math.sin(b)
        yaw = math.degrees(math.atan2(cy - py, cx - px))
        hold([px, py, z_fly], yaw, ticks=8)
        state, img = hold([px, py, z_fly], yaw, sonar_grab=True)
        key = f"b{int(bearing):03d}_r{int(rng):02d}"
        if img is None:
            print(f"[cond {args.condition}] WARNING no frame at {key}")
            continue
        actual = np.asarray(state["LocationSensor"], dtype=float)
        frames[key] = img
        poses_actual[key] = {"commanded": [px, py, z_fly, yaw],
                             "actual_xyz": [round(float(v), 4) for v in actual]}
        print(f"[cond {args.condition}] {key} captured")

    np.savez_compressed(out / f"frames_{args.condition}.npz", **frames)
    (out / f"poses_{args.condition}.json").write_text(
        json.dumps({"bed_z": bed_z, "poses": poses_actual}, indent=2),
        encoding="utf-8")
    print(f"[cond {args.condition}] DONE ({len(frames)}/{len(POSES)} poses)")
    return 0


def analyze(args) -> int:
    out = Path(args.out)
    data = {}
    for cond in CONDITIONS:
        p = out / f"frames_{cond}.npz"
        if p.exists():
            data[cond] = dict(np.load(p))
    if "A" not in data or "FULL" not in data:
        print("[analyze] need at least conditions A and FULL")
        return 1

    # geometry-derived expected windows: nearest/farthest structure surface
    # per pose from the scene manifest of FULL
    manifest = json.loads((out / "scene_FULL.json").read_text(encoding="utf-8"))
    comp_xy = [(c["location"][0], c["location"][1])
               for c in manifest["components"]]
    poses_meta = json.loads((out / "poses_FULL.json").read_text(
        encoding="utf-8"))["poses"]

    def rows(n):
        return np.linspace(SONAR["rmin"], SONAR["rmax"], n)

    report = {"conditions": {c: sorted(data[c].keys()) for c in data},
              "pose_repeatability_m": {}, "per_pose": {}}

    # pose repeatability across sessions (actual positions)
    all_pose_files = sorted(out.glob("poses_*.json"))
    for key in sorted(data["A"].keys()):
        pts = []
        for pf in all_pose_files:
            meta = json.loads(pf.read_text(encoding="utf-8"))["poses"]
            if key in meta:
                pts.append(meta[key]["actual_xyz"][:3])
        if len(pts) >= 2:
            pts = np.asarray(pts)
            report["pose_repeatability_m"][key] = round(
                float(np.linalg.norm(pts - pts.mean(0), axis=1).max()), 4)

    for key, ref in data["A"].items():
        if key not in poses_meta:
            continue
        px, py = poses_meta[key]["commanded"][:2]
        dists = [math.hypot(px - x, py - y) for x, y in comp_xy]
        r_lo = max(SONAR["rmin"], min(dists) - 2.0)
        r_hi = min(SONAR["rmax"], max(dists) + 2.0)
        r = rows(ref.shape[0])
        win = (r >= r_lo) & (r <= r_hi)
        outw = ~win & (r > 4.0)
        entry = {"expected_window_m": [round(r_lo, 1), round(r_hi, 1)]}
        for cond, frames in data.items():
            if cond == "A" or key not in frames:
                continue
            diff = np.abs(frames[key] - ref)
            in_w = float(diff[win, :].mean())
            out_w = float(diff[outw, :].mean()) if outw.any() else 0.0
            changed = int((diff > 1e-9).sum())
            entry[cond] = {"in_window_mad": round(in_w, 6),
                           "out_window_mad": round(out_w, 6),
                           "contrast_ratio": round(in_w / max(out_w, 1e-9), 2),
                           "changed_bins": changed}
        report["per_pose"][key] = entry

    # condition-level summary
    summary = {}
    for cond in data:
        if cond == "A":
            continue
        ratios = [v[cond]["contrast_ratio"] for v in report["per_pose"].values()
                  if cond in v]
        inws = [v[cond]["in_window_mad"] for v in report["per_pose"].values()
                if cond in v]
        if ratios:
            summary[cond] = {
                "poses": len(ratios),
                "median_contrast_ratio": round(float(np.median(ratios)), 2),
                "median_in_window_mad": round(float(np.median(inws)), 6),
            }
    report["summary"] = summary
    (out / "analysis.json").write_text(json.dumps(report, indent=2),
                                       encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"[analyze] pose repeatability (max dev): "
          f"{report['pose_repeatability_m']}")
    print(f"[analyze] DONE -> {out / 'analysis.json'}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--condition", choices=CONDITIONS)
    ap.add_argument("--analyze", action="store_true")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    if args.analyze:
        return analyze(args)
    if not args.condition:
        print("need --condition or --analyze")
        return 2
    return run_condition(args)


if __name__ == "__main__":
    raise SystemExit(main())

"""Minimal, rigorous sonar visibility truth test (custom OR official engine).

Answers one question directly: does a RUNTIME-SPAWNED object appear in the
sonar image? Each condition places one object dead-ahead of the ROV's sonar
at a controlled pose and captures the raw frame; a baseline with no object is
the reference. Difference against the baseline = the object's acoustic
signature (if any).

Conditions:
    A        nothing spawned (baseline)
    BOX      a 2 m cube on the seabed at the target point
    CYL      a 0.5 m x 4 m vertical cylinder at the target point
    OUTFALL  the full BrineWatch multiport outfall (OutfallSceneBuilder),
             diffuser centre at the target point

Engines:
    custom   the fork engine (runtime octree rebuild) via attach mode; ONE
             fresh engine session per condition (driver clears the octree
             cache before each boot). Requires the engine to be already
             running (scripts/launch_custom_engine.py).
    official the unmodified HoloOcean 2.3.0 engine, launched in-process; all
             conditions captured in ONE session (spawned props never enter
             the official octree, so there is no cross-condition contamination
             to avoid).

Per invocation captures ONE condition (custom) or ALL conditions (official).
`--analyze DIR` produces the diff stats, PNGs, JSON and markdown report.

No ground truth is used for detection; the true object position is only used
to place the ROV pose and (in analysis) to derive the expected echo window.
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

# Per-engine site (custom = fork ExampleLevel; official = FlatUnderwater).
SITES = {
    "custom": {"world": "ExampleLevel", "target": (30.0, 0.0), "boot_z": -40.0},
    "official": {"world": "FlatUnderwater", "target": (100.0, 50.0), "boot_z": -10.0},
}
SONAR = {"rmin": 1.0, "rmax": 40.0, "az": 120.0, "elev": 20.0,
         "range_bins": 512, "az_bins": 256}
HEADON_RANGE = 15.0          # ROV sits this far south of the target, looking N
CONDITIONS = ("A", "BOX", "CYL", "OUTFALL")


def _sonar_cfg():
    return {"RangeBins": SONAR["range_bins"], "AzimuthBins": SONAR["az_bins"],
            "RangeMin": SONAR["rmin"], "RangeMax": SONAR["rmax"],
            "InitOctreeRange": 50.0, "Elevation": SONAR["elev"],
            "Azimuth": SONAR["az"], "TicksPerCapture": 30,
            "AddSigma": 0.0, "MultSigma": 0.0, "ViewOctree": -1}


def _scenario(world, boot_z):
    return {
        "name": "sonar_truth", "world": world, "package_name": "Ocean",
        "main_agent": AGENT, "ticks_per_sec": 30, "frames_per_sec": False,
        "agents": [{
            "agent_name": AGENT, "agent_type": "BlueROV2",
            "sensors": [
                {"sensor_type": "LocationSensor", "socket": "IMUSocket"},
                {"sensor_type": "RangeFinderSensor", "socket": "SonarSocket",
                 "configuration": {"LaserCount": 4, "LaserAngle": -90,
                                   "LaserMaxDistance": 200}},
                {"sensor_type": "ImagingSonar", "socket": "SonarSocket",
                 "configuration": _sonar_cfg()},
            ],
            "control_scheme": 1,
            "location": [SITES_boot(world)[0], SITES_boot(world)[1], boot_z],
            "rotation": [0.0, 0.0, 90.0],
        }],
    }


def SITES_boot(world):
    for s in SITES.values():
        if s["world"] == world:
            tx, ty = s["target"]
            return (tx, ty - HEADON_RANGE - 30.0)  # boot well clear of objects
    return (0.0, 0.0)


def _hold(env, agent, pos, yaw, ticks=10, grab_sonar=False):
    cmd = np.array([*pos, 0.0, 0.0, yaw], dtype=np.float64)
    state, frame = None, None
    n = 300 if grab_sonar else ticks
    for _ in range(n):
        agent.teleport(list(pos), [0.0, 0.0, yaw])
        env.act(AGENT, cmd)
        state = env.tick()
        if grab_sonar and "ImagingSonar" in state:
            frame = np.asarray(state["ImagingSonar"], dtype=float).copy()
            break
    return state, frame


def _probe_bed(env, agent, tx, ty, boot_z):
    for hz in (boot_z, -30.0, -80.0, -150.0):
        state, _ = _hold(env, agent, [tx, ty, hz], 90.0, ticks=12)
        rf = np.asarray(state["RangeFinderSensor"], dtype=float)
        valid = rf[rf > 0.5]
        loc = np.asarray(state["LocationSensor"], dtype=float)
        if valid.size:
            return float(loc[2]) - float(valid.min())
    return None


def _spawn_condition(condition, env, spawn_fn, tx, ty, bed_z):
    """Spawn the object(s) for a condition; return a manifest dict or None."""
    if condition == "A":
        return {"objects": []}
    if condition == "BOX":
        spawn_fn("box", location=[tx, ty, bed_z + 1.0],
                 rotation=[0.0, 0.0, 0.0], scale=[2.0, 2.0, 2.0], material="steel")
        return {"objects": [{"type": "box", "xy": [tx, ty], "scale": [2, 2, 2]}]}
    if condition == "CYL":
        spawn_fn("cylinder", location=[tx, ty, bed_z + 2.0],
                 rotation=[0.0, 0.0, 0.0], scale=[0.5, 0.5, 4.0], material="steel")
        return {"objects": [{"type": "cylinder", "xy": [tx, ty], "scale": [0.5, 0.5, 4]}]}
    if condition == "OUTFALL":
        from brinewatch.simulation.outfall_scene import (
            OutfallSceneBuilder, OutfallSceneConfig)
        from brinewatch.utils.config import OutfallConfig
        from brinewatch.utils.terrain import TerrainMap
        L = OutfallSceneConfig().diffuser_length_m
        ox, oy = tx - L / 2.0, ty      # diffuser centre lands on the target
        xs = np.linspace(ox - 60, ox + 60, 13)
        ys = np.linspace(oy - 60, oy + 60, 13)
        builder = OutfallSceneBuilder(
            env=env, agent_name=AGENT,
            outfall=OutfallConfig(x=ox, y=oy, axis_deg=0.0, n_ports=6,
                                  port_spacing_m=3.2),
            scene=OutfallSceneConfig(structure_yaw_deg=0.0, scatter_rocks=0),
            terrain=TerrainMap(xs, ys, np.full((13, 13), bed_z)),
            spawn_fn=spawn_fn)
        builder.build()
        return {"objects": [{"type": "outfall", "origin_xy": [ox, oy],
                             "diffuser_centre_xy": [tx, ty],
                             "components": sum(1 for c in builder.components if c.ok)}]}
    raise ValueError(condition)


def _capture(env, agent, tx, ty, bed_z):
    """Capture the head-on frame plus two flanking oblique frames."""
    frames, meta = {}, {}
    poses = [("headon", tx, ty - HEADON_RANGE, 90.0),
             ("left45", tx - 12.0, ty - 12.0, 45.0),
             ("right45", tx + 12.0, ty - 12.0, 135.0)]
    z = bed_z + 3.0
    for key, px, py, yaw in poses:
        _hold(env, agent, [px, py, z], yaw, ticks=10)
        state, img = _hold(env, agent, [px, py, z], yaw, grab_sonar=True)
        if img is None:
            print(f"[capture] WARNING no frame at {key}")
            continue
        loc = np.asarray(state["LocationSensor"], dtype=float)
        frames[key] = img
        meta[key] = {"commanded": [px, py, z, yaw],
                     "actual_xyz": [round(float(v), 4) for v in loc]}
        print(f"[capture] {key}")
    return frames, meta


# --------------------------------------------------------------------------- #
def run_custom(args) -> int:
    from brinewatch.simulation.custom_engine import (
        activate_fork_client, attach_custom_environment,
        discover_custom_engine, make_asset_spawner)
    engine = discover_custom_engine(level=SITES["custom"]["world"])
    holoocean = activate_fork_client(engine)
    tx, ty = SITES["custom"]["target"]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    scenario = _scenario(engine.level, SITES["custom"]["boot_z"])
    env = attach_custom_environment(holoocean, scenario,
                                    show_viewport=True, verbose=False)
    env.reset()
    agent = env.agents[AGENT]
    print(f"[custom {args.condition}] attached (client "
          f"{'fork ' + engine.client_src.as_posix() if engine.client_src else 'official'})")
    bed_z = _probe_bed(env, agent, tx, ty, SITES["custom"]["boot_z"])
    print(f"[custom {args.condition}] bed z = {bed_z:.2f}")

    spawn = make_asset_spawner(env, holoocean, label_prefix=f"truth_{args.condition}")
    manifest = _spawn_condition(args.condition, env, spawn, tx, ty, bed_z)
    if args.condition != "A":
        env.tick()
        time.sleep(1.2)   # let the sonar tick consume the dirty flag + rebuild
    frames, meta = _capture(env, agent, tx, ty, bed_z)
    np.savez_compressed(out / f"custom_{args.condition}.npz", **frames)
    (out / f"custom_{args.condition}.json").write_text(json.dumps(
        {"engine": "custom", "condition": args.condition, "bed_z": bed_z,
         "target": [tx, ty], "manifest": manifest, "poses": meta}, indent=2),
        encoding="utf-8")
    print(f"[custom {args.condition}] DONE {len(frames)} poses")
    return 0


def run_official(args) -> int:
    import holoocean
    tx, ty = SITES["official"]["target"]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    scenario = _scenario(SITES["official"]["world"], SITES["official"]["boot_z"])
    env = holoocean.make(scenario_cfg=scenario, show_viewport=True, verbose=False)
    agent = env.agents[AGENT]
    print("[official] launched")
    bed_z = _probe_bed(env, agent, tx, ty, SITES["official"]["boot_z"])
    print(f"[official] bed z = {bed_z:.2f}")

    # official props never enter the octree -> capture every condition in one
    # session, spawning cumulatively is fine (all should read == baseline A)
    for cond in CONDITIONS:
        manifest = _spawn_condition(cond, env, env.spawn_prop, tx, ty, bed_z)
        if cond != "A":
            for _ in range(30):
                env.tick()
        frames, meta = _capture(env, agent, tx, ty, bed_z)
        np.savez_compressed(out / f"official_{cond}.npz", **frames)
        (out / f"official_{cond}.json").write_text(json.dumps(
            {"engine": "official", "condition": cond, "bed_z": bed_z,
             "target": [tx, ty], "manifest": manifest, "poses": meta}, indent=2),
            encoding="utf-8")
        print(f"[official {cond}] DONE {len(frames)} poses")
    return 0


def analyze(args) -> int:
    out = Path(args.out)

    def stats(img):
        return {"max": round(float(img.max()), 5),
                "mean": round(float(img.mean()), 6),
                "nonzero_bins": int((img > 0).sum()),
                "nonzero_frac": round(float((img > 0).mean()), 5)}

    report = {"engines": {}}
    md = ["# Sonar visibility truth test\n",
          "Runtime-spawned object dead-ahead of the sonar; difference against "
          "the no-object baseline (A) is the object's acoustic signature.\n"]
    for engine in ("official", "custom"):
        base_p = out / f"{engine}_A.npz"
        if not base_p.exists():
            continue
        base = dict(np.load(base_p))
        eng_rep = {}
        md.append(f"\n## {engine} engine\n")
        md.append("| condition | pose | max | nonzero bins | mean|diff| vs A | bit-identical to A |")
        md.append("|---|---|---|---|---|---|")
        for cond in CONDITIONS:
            p = out / f"{engine}_{cond}.npz"
            if not p.exists():
                continue
            frames = dict(np.load(p))
            cond_rep = {}
            for key in sorted(frames):
                img = frames[key]
                entry = stats(img)
                if key in base:
                    diff = np.abs(img - base[key])
                    entry["mad_vs_A"] = round(float(diff.mean()), 6)
                    entry["identical_to_A"] = bool(np.array_equal(img, base[key]))
                    entry["changed_bins"] = int((diff > 1e-9).sum())
                cond_rep[key] = entry
                md.append(f"| {cond} | {key} | {entry['max']} | "
                          f"{entry['nonzero_bins']} | "
                          f"{entry.get('mad_vs_A', '-')} | "
                          f"{entry.get('identical_to_A', '-')} |")
                # PNG
                try:
                    import matplotlib
                    matplotlib.use("Agg")
                    import matplotlib.pyplot as plt
                    fig, ax = plt.subplots(1, 2, figsize=(9, 4))
                    ax[0].imshow(np.log1p(img), aspect="auto", cmap="viridis",
                                 extent=[-SONAR["az"] / 2, SONAR["az"] / 2,
                                         SONAR["rmax"], SONAR["rmin"]])
                    ax[0].set_title(f"{engine} {cond} {key}")
                    ax[0].set_ylabel("range (m)")
                    if key in base:
                        ax[1].imshow(np.log1p(np.abs(img - base[key])),
                                     aspect="auto", cmap="inferno",
                                     extent=[-SONAR["az"] / 2, SONAR["az"] / 2,
                                             SONAR["rmax"], SONAR["rmin"]])
                        ax[1].set_title(f"|{cond} - A|")
                    fig.tight_layout()
                    fig.savefig(out / f"{engine}_{cond}_{key}.png", dpi=90)
                    plt.close(fig)
                except Exception as exc:
                    print("png error:", exc)
            eng_rep[cond] = cond_rep
        report["engines"][engine] = eng_rep

    # verdicts
    verdicts = {}
    for engine, eng_rep in report["engines"].items():
        for cond in ("BOX", "CYL", "OUTFALL"):
            if cond not in eng_rep:
                continue
            headon = eng_rep[cond].get("headon", {})
            visible = (not headon.get("identical_to_A", True)) and \
                      headon.get("changed_bins", 0) > 50
            verdicts[f"{engine}:{cond}"] = {
                "visible": bool(visible),
                "changed_bins_headon": headon.get("changed_bins"),
                "mad_headon": headon.get("mad_vs_A")}
    report["verdicts"] = verdicts
    md.append("\n## Verdicts (head-on pose)\n")
    md.append("| engine:condition | spawned object visible? | changed bins | mean|diff| |")
    md.append("|---|---|---|---|")
    for k, v in verdicts.items():
        md.append(f"| {k} | **{'YES' if v['visible'] else 'NO'}** | "
                  f"{v['changed_bins_headon']} | {v['mad_headon']} |")

    (out / "truth_test_summary.json").write_text(json.dumps(report, indent=2),
                                                 encoding="utf-8")
    (out / "truth_test_report.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md[-10:]))
    print(f"\n[analyze] DONE -> {out}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--engine", choices=["custom", "official"])
    ap.add_argument("--condition", choices=CONDITIONS)
    ap.add_argument("--analyze", action="store_true")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    if args.analyze:
        return analyze(args)
    if args.engine == "custom":
        if not args.condition:
            print("custom mode needs --condition")
            return 2
        return run_custom(args)
    if args.engine == "official":
        return run_official(args)
    print("need --engine or --analyze")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Sonar visibility gate: is a runtime-spawned structure visible to the
official HoloOcean ImagingSonar?

This is the controlled experiment behind every "sonar-based" claim in the
PFH 2026 application. It runs two conditions in separate engine processes:

- ``present``: octree cache cleared -> environment created -> test structure
  spawned via the official ``spawn_prop`` BEFORE the first tick -> sonar
  frames collected at several known poses (official agent teleport);
- ``absent``:  identical in every respect, but nothing is spawned.

The analysis then compares mean sonar intensity inside the range/azimuth
bins where the structure should appear, between the two conditions, at each
pose, and produces a per-pose z-score contrast plus rendered images and a
machine-readable summary.

Usage (orchestrator; runs both conditions as subprocesses):

    python scripts/validate_sonar_visibility.py

Worker mode (used internally):

    python scripts/validate_sonar_visibility.py --capture present --out <dir>

Only official HoloOcean 2.x APIs are used: scenario dicts, spawn_prop,
agent teleport, ImagingSonar, delete_world_octrees.
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

WORLD = "SimpleUnderwater"
AGENT = "sonar_probe"

# Target structure location (world frame). The vehicle approaches from -x.
TARGET_XY = (12.0, 0.0)
# Sonar configuration used for the gate (no noise: cleanest possible signal).
SONAR_CFG = {
    "RangeMin": 0.5,
    "RangeMax": 35.0,
    "RangeBins": 512,
    "AzimuthBins": 256,
    "Azimuth": 120.0,
    "Elevation": 20.0,
    "InitOctreeRange": 60.0,
    "ShowWarning": False,
}
# Vehicle poses: (range to target in m). Vehicle flies ~2 m above the bed so
# a bed-mounted structure falls inside the +-10 deg elevation fan.
POSE_RANGES = [8.0, 12.0, 18.0]
FRAMES_PER_POSE = 12
KEEP_LAST = 6
SETTLE_TICKS = 90  # PID settle + octree generation headroom per pose


def scenario() -> dict:
    return {
        "name": "sonar_visibility_gate",
        "package_name": "Ocean",
        "world": WORLD,
        "main_agent": AGENT,
        "ticks_per_sec": 30,
        "frames_per_sec": False,
        "octree_min": 0.05,
        "octree_max": 5.0,
        "agents": [
            {
                "agent_name": AGENT,
                "agent_type": "BlueROV2",
                "sensors": [
                    {"sensor_type": "PoseSensor", "socket": "IMUSocket"},
                    {"sensor_type": "LocationSensor", "socket": "IMUSocket"},
                    {"sensor_type": "RangeFinderSensor", "socket": "SonarSocket",
                     "configuration": {"LaserCount": 4, "LaserAngle": -90,
                                       "LaserMaxDistance": 60}},
                    {"sensor_type": "ImagingSonar", "socket": "SonarSocket",
                     "configuration": dict(SONAR_CFG)},
                ],
                "control_scheme": 1,
                "location": [TARGET_XY[0] - POSE_RANGES[0], TARGET_XY[1], -28.0],
                "rotation": [0.0, 0.0, 0.0],
            }
        ],
        "window_width": 768,
        "window_height": 432,
    }


def spawn_test_structure(env, bed_z: float) -> list:
    """Spawn the proto-outfall test target (manifold box + 3 risers).

    Returns the manifest of spawned components. Uses only official
    ``spawn_prop``. Sized generously so the acoustic answer is unambiguous."""
    manifest = []
    x, y = TARGET_XY
    parts = [
        ("box", [x, y, bed_z + 0.6], [0.0, 0.0, 90.0], [6.0, 1.0, 1.2]),
        ("cylinder", [x, y - 2.0, bed_z + 1.4], [0.0, 0.0, 0.0], [0.5, 0.5, 1.8]),
        ("cylinder", [x, y, bed_z + 1.4], [0.0, 0.0, 0.0], [0.5, 0.5, 1.8]),
        ("cylinder", [x, y + 2.0, bed_z + 1.4], [0.0, 0.0, 0.0], [0.5, 0.5, 1.8]),
    ]
    for prop_type, loc, rot, scale in parts:
        env.spawn_prop(prop_type, location=loc, rotation=rot, scale=scale,
                       sim_physics=False, material="steel")
        manifest.append({"type": prop_type, "location": loc, "rotation": rot,
                         "scale": scale, "material": "steel"})
    return manifest


def measure_bed_z(env, x: float, y: float, hold_z: float = -25.0) -> float:
    """Teleport above (x, y), read the down-looking RangeFinder, return bed z."""
    agent = env.agents[AGENT]
    cmd = np.array([x, y, hold_z, 0.0, 0.0, 0.0], dtype=np.float64)
    agent.teleport([x, y, hold_z], [0.0, 0.0, 0.0])
    state = None
    for _ in range(40):
        env.act(AGENT, cmd)
        state = env.tick()
    ranges = np.asarray(state["RangeFinderSensor"], dtype=float)
    valid = ranges[ranges > 0]
    if not valid.size:
        raise RuntimeError(f"RangeFinder saw no bottom at ({x:.1f},{y:.1f})")
    z = float(np.asarray(state["LocationSensor"], dtype=float)[2])
    return z - float(valid.min())


def run_capture(condition: str, out_dir: Path) -> None:
    """Worker: one engine process, one condition, frames saved to out_dir."""
    import holoocean

    from brinewatch.simulation.octree_cache import clear_world_octrees

    out_dir.mkdir(parents=True, exist_ok=True)
    clear_world_octrees(WORLD)

    env = holoocean.make(scenario_cfg=scenario(), show_viewport=True, verbose=False)
    agent = env.agents[AGENT]

    # 1) measure the real seabed under the target BEFORE spawning anything
    bed_z = measure_bed_z(env, TARGET_XY[0], TARGET_XY[1])
    print(f"[worker:{condition}] measured bed z at target: {bed_z:.2f}")

    # 2) spawn the structure (present condition only) BEFORE any sonar frame
    manifest = []
    if condition == "present":
        manifest = spawn_test_structure(env, bed_z)
        print(f"[worker:{condition}] spawned {len(manifest)} components")

    # 3) collect sonar frames at each pose (teleport + PID hold)
    records = []
    for rng in POSE_RANGES:
        px = TARGET_XY[0] - rng
        py = TARGET_XY[1]
        pz = bed_z + 2.0
        cmd = np.array([px, py, pz, 0.0, 0.0, 0.0], dtype=np.float64)
        agent.teleport([px, py, pz], [0.0, 0.0, 0.0])
        for _ in range(SETTLE_TICKS):
            env.act(AGENT, cmd)
            state = env.tick()
        frames = []
        for _ in range(FRAMES_PER_POSE):
            env.act(AGENT, cmd)
            state = env.tick()
            if "ImagingSonar" in state:
                frames.append(np.asarray(state["ImagingSonar"], dtype=np.float32))
        frames = np.stack(frames[-KEEP_LAST:]) if frames else np.zeros((0,))
        loc = np.asarray(state["LocationSensor"], dtype=float)
        records.append({"range_m": rng, "pose": [float(loc[0]), float(loc[1]), float(loc[2])],
                        "n_frames": int(frames.shape[0])})
        np.save(out_dir / f"frames_r{rng:.0f}.npy", frames)
        print(f"[worker:{condition}] pose r={rng:.0f} m: {frames.shape[0]} frames, "
              f"max={float(frames.max()) if frames.size else 0:.4f}")

    meta = {
        "condition": condition,
        "world": WORLD,
        "target_xy": TARGET_XY,
        "bed_z_measured": bed_z,
        "sonar_config": SONAR_CFG,
        "poses": records,
        "structure_manifest": manifest,
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"[worker:{condition}] DONE -> {out_dir}")


# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #
def target_mask(shape, rng: float) -> np.ndarray:
    """Boolean mask of (range, azimuth) bins where the structure should sit."""
    n_r, n_a = shape
    r_lo = (rng - 2.5 - SONAR_CFG["RangeMin"]) / (SONAR_CFG["RangeMax"] - SONAR_CFG["RangeMin"])
    r_hi = (rng + 3.5 - SONAR_CFG["RangeMin"]) / (SONAR_CFG["RangeMax"] - SONAR_CFG["RangeMin"])
    az_half = math.degrees(math.atan2(4.0, rng)) / SONAR_CFG["Azimuth"]  # +-4 m wide target
    mask = np.zeros((n_r, n_a), dtype=bool)
    r0, r1 = int(max(0, r_lo * n_r)), int(min(n_r, r_hi * n_r))
    a0 = int(max(0, (0.5 - az_half) * n_a))
    a1 = int(min(n_a, (0.5 + az_half) * n_a))
    mask[r0:r1, a0:a1] = True
    return mask


def render_png(arr: np.ndarray, path: Path, title: str) -> None:
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


def analyze(out_root: Path) -> dict:
    summary = {"world": WORLD, "sonar": "ImagingSonar", "poses": [], "visible": False}
    visible_votes = 0
    for rng in POSE_RANGES:
        fp = out_root / "present" / f"frames_r{rng:.0f}.npy"
        fa = out_root / "absent" / f"frames_r{rng:.0f}.npy"
        pres = np.load(fp)
        abse = np.load(fa)
        if pres.size == 0 or abse.size == 0:
            summary["poses"].append({"range_m": rng, "error": "missing frames"})
            continue
        mp, ma = pres.mean(axis=0), abse.mean(axis=0)
        mask = target_mask(mp.shape, rng)
        in_p = float(mp[mask].mean())
        in_a = float(ma[mask].mean())
        bg_std = float(ma[mask].std()) + 1e-9
        z = (in_p - in_a) / bg_std
        ratio = in_p / (in_a + 1e-9)
        pose_visible = bool(z > 5.0 and ratio > 2.0)
        visible_votes += int(pose_visible)
        summary["poses"].append({
            "range_m": rng, "mask_mean_present": in_p, "mask_mean_absent": in_a,
            "z_score": round(z, 2), "ratio": round(ratio, 2), "visible": pose_visible,
        })
        render_png(mp, out_root / f"sonar_present_r{rng:.0f}.png",
                   f"ImagingSonar — structure present, {rng:.0f} m")
        render_png(ma, out_root / f"sonar_absent_r{rng:.0f}.png",
                   f"ImagingSonar — structure absent, {rng:.0f} m")
        render_png(np.abs(mp - ma), out_root / f"sonar_diff_r{rng:.0f}.png",
                   f"|present − absent|, {rng:.0f} m")
    summary["visible"] = visible_votes >= 2
    summary["visible_votes"] = visible_votes
    (out_root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    lines = ["# Sonar visibility gate — results", "",
             f"World: {WORLD} · Sensor: official ImagingSonar · conditions run in",
             "separate engine processes with the octree cache cleared each time", ""]
    for p in summary["poses"]:
        lines.append(f"- r={p['range_m']:.0f} m: z={p.get('z_score')} "
                     f"ratio={p.get('ratio')} visible={p.get('visible')}")
    lines.append("")
    lines.append(f"**VERDICT: {'VISIBLE' if summary['visible'] else 'NOT VISIBLE'}** "
                 f"({visible_votes}/{len(POSE_RANGES)} poses)")
    (out_root / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--capture", choices=["present", "absent"], default=None)
    ap.add_argument("--out", type=str, default=None)
    args = ap.parse_args()

    if args.capture:
        run_capture(args.capture, Path(args.out))
        return 0

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_root = REPO_ROOT / "outputs" / f"sonar_visibility_{stamp}"
    out_root.mkdir(parents=True, exist_ok=True)
    for condition in ("present", "absent"):
        print(f"=== capturing condition: {condition} ===")
        res = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--capture", condition,
             "--out", str(out_root / condition)],
            timeout=900,
        )
        if res.returncode != 0:
            print(f"capture '{condition}' FAILED (exit {res.returncode})")
            return 1
    summary = analyze(out_root)
    print(json.dumps(summary, indent=2))
    print(f"outputs: {out_root}")
    return 0 if summary["visible"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

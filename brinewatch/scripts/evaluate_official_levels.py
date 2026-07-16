"""Evaluate one official Ocean world as a candidate outfall demonstration site.

Run once per world (single-engine constraint; crash isolation):

    python scripts/evaluate_official_levels.py --world Dam
    python scripts/evaluate_official_levels.py --world ExampleLevel --scan 150
    python scripts/evaluate_official_levels.py --world FlatUnderwater --sites "100 50" --sonar

Pipeline per world:
1. coarse RangeFinder scan over a grid -> usable-water map (bed depth, relief)
2. pick the best candidate sites (flat, deep enough, away from walls) unless
   --sites is given
3. per site: 9x9 local probe (relief stats), spawn the v2 outfall (official
   spawn_prop adapter), capture 3 RGB views + viewport plan view, luminance
4. optional --sonar: capture ImagingSonar frames at 2 bearings -> native
   clutter metrics (official sonar sees ONLY static level geometry = clutter)
5. write outputs/level_eval/<world>/report.json + contact sheet

The SAME v2 outfall geometry is used everywhere (OutfallSceneBuilder).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

AGENT = "eval"


def make_env(world: str, sonar: bool):
    import holoocean

    sensors = [
        {"sensor_type": "LocationSensor", "socket": "IMUSocket"},
        {"sensor_type": "RangeFinderSensor", "socket": "SonarSocket",
         "configuration": {"LaserCount": 4, "LaserAngle": -90,
                           "LaserMaxDistance": 300}},
        {"sensor_type": "RGBCamera", "socket": "CameraSocket",
         "configuration": {"CaptureWidth": 960, "CaptureHeight": 540}},
        {"sensor_type": "ViewportCapture",
         "configuration": {"CaptureWidth": 800, "CaptureHeight": 450}},
    ]
    if sonar:
        sensors.append(
            {"sensor_type": "ImagingSonar", "socket": "SonarSocket",
             "configuration": {"RangeBins": 512, "AzimuthBins": 256,
                               "RangeMin": 1.0, "RangeMax": 40.0,
                               "InitOctreeRange": 50.0, "Elevation": 20.0,
                               "Azimuth": 120.0, "TicksPerCapture": 30,
                               "AddSigma": 0.0, "MultSigma": 0.0,
                               "ViewOctree": -1}})
    scenario = {
        "name": f"level_eval_{world}", "package_name": "Ocean", "world": world,
        "main_agent": AGENT, "ticks_per_sec": 30, "frames_per_sec": False,
        "agents": [{"agent_name": AGENT, "agent_type": "BlueROV2",
                    "sensors": sensors, "control_scheme": 1,
                    "location": [0.0, 0.0, -5.0],
                    "rotation": [0.0, 0.0, 0.0]}],
        "window_width": 800, "window_height": 450,
    }
    return holoocean.make(scenario_cfg=scenario, show_viewport=True,
                          verbose=False)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--world", required=True)
    ap.add_argument("--scan", type=float, default=120.0,
                    help="half-span of the coarse scan grid (m)")
    ap.add_argument("--grid", type=int, default=7)
    ap.add_argument("--sites", nargs="*", default=None,
                    help='explicit sites as "x y" strings, skip auto-pick')
    ap.add_argument("--sonar", action="store_true",
                    help="capture native-clutter sonar frames (slow first run)")
    ap.add_argument("--max-sites", type=int, default=2)
    args = ap.parse_args()

    out = REPO / "outputs" / "level_eval" / args.world
    out.mkdir(parents=True, exist_ok=True)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    env = make_env(args.world, args.sonar)
    agent = env.agents[AGENT]
    print(f"[eval] {args.world}: engine up")

    def hold(pos, yaw, pitch=0.0, ticks=12, sonar_grab=False):
        cmd = np.array([*pos, 0.0, pitch, yaw], dtype=np.float64)
        state, frame = None, None
        n = 240 if sonar_grab else ticks
        for _ in range(n):
            agent.teleport(list(pos), [0.0, pitch, yaw])
            env.act(AGENT, cmd)
            state = env.tick()
            if sonar_grab and "ImagingSonar" in state:
                frame = np.asarray(state["ImagingSonar"], dtype=float).copy()
                break
        return state, frame

    def bed_at(x, y):
        for hold_z in (-5.0, -30.0, -80.0, -150.0):
            state, _ = hold([x, y, hold_z], 0.0, ticks=8)
            rf = np.asarray(state["RangeFinderSensor"], dtype=float)
            valid = rf[rf > 0.5]
            loc = np.asarray(state["LocationSensor"], dtype=float)
            if valid.size:
                return float(loc[2]) - float(valid.min())
        return None

    # ---- 1. coarse scan --------------------------------------------------- #
    xs = np.linspace(-args.scan, args.scan, args.grid)
    ys = np.linspace(-args.scan, args.scan, args.grid)
    beds = np.full((args.grid, args.grid), np.nan)
    for i, x in enumerate(xs):
        for j, y in enumerate(ys):
            b = bed_at(float(x), float(y))
            if b is not None:
                beds[j, i] = b
    n_wet = int(np.isfinite(beds).sum())
    print(f"[eval] scan: {n_wet}/{beds.size} usable soundings; "
          f"bed range [{np.nanmin(beds):.1f}, {np.nanmax(beds):.1f}]"
          if n_wet else f"[eval] scan: NO usable water found")
    np.savez(out / "scan.npz", xs=xs, ys=ys, beds=beds)

    report = {"world": args.world, "stamp": datetime.now().isoformat(),
              "scan_half_span_m": args.scan,
              "usable_soundings": n_wet, "grid": args.grid,
              "bed_min": None if not n_wet else round(float(np.nanmin(beds)), 2),
              "bed_max": None if not n_wet else round(float(np.nanmax(beds)), 2),
              "sites": []}
    if not n_wet:
        (out / "report.json").write_text(json.dumps(report, indent=2))
        print("[eval] world unusable; report written")
        return 0

    # ---- 2. candidate sites ----------------------------------------------- #
    if args.sites:
        sites = [tuple(float(v) for v in s.split()) for s in args.sites]
    else:
        # local flatness over 3x3 neighbourhoods; deepest+flattest first
        cands = []
        for i in range(1, args.grid - 1):
            for j in range(1, args.grid - 1):
                w = beds[j - 1:j + 2, i - 1:i + 2]
                if np.isfinite(w).all() and w.min() < -8.0:
                    cands.append((float(np.ptp(w)), float(xs[i]), float(ys[j])))
        cands.sort()
        sites = [(x, y) for _, x, y in cands[:args.max_sites]]
    print(f"[eval] candidate sites: {sites}")

    from brinewatch.simulation.outfall_scene import (
        OutfallSceneBuilder, OutfallSceneConfig,
    )
    from brinewatch.utils.config import OutfallConfig
    from brinewatch.utils.terrain import TerrainMap

    for s_idx, (sx, sy) in enumerate(sites):
        tag = f"site{s_idx}_{int(sx)}_{int(sy)}"
        # local 9x9 probe
        lx = np.linspace(sx - 40, sx + 40, 9)
        ly = np.linspace(sy - 40, sy + 40, 9)
        lz = np.full((9, 9), np.nan)
        for i, x in enumerate(lx):
            for j, y in enumerate(ly):
                b = bed_at(float(x), float(y))
                if b is not None:
                    lz[j, i] = b
        if not np.isfinite(lz).all():
            print(f"[eval] {tag}: incomplete local probe, skipping")
            continue
        relief = float(np.ptp(lz))
        bed0 = float(np.nanmedian(lz))
        site_info = {"xy": [sx, sy], "bed_median": round(bed0, 2),
                     "local_relief_m": round(relief, 2)}

        # spawn the v2 outfall with auto-orientation
        terrain = TerrainMap(lx, ly, lz)
        builder = OutfallSceneBuilder(
            env=env, agent_name=AGENT,
            outfall=OutfallConfig(x=sx, y=sy, axis_deg=0.0, n_ports=6,
                                  port_spacing_m=3.2),
            scene=OutfallSceneConfig(scatter_rocks=0), terrain=terrain)
        try:
            builder.auto_orient()
            builder.build()
            built = sum(1 for c in builder.components if c.ok)
            site_info["components_built"] = built
            yaw = math.degrees(builder._yaw_rad)
            site_info["structure_yaw_deg"] = round(yaw, 1)
        except Exception as exc:
            site_info["build_error"] = str(exc)
            report["sites"].append(site_info)
            print(f"[eval] {tag}: build failed: {exc}")
            continue
        builder.save_manifest(out / f"{tag}_scene_manifest.json")

        # RGB views (agent camera): three-quarter, side, close
        L = builder.scene.diffuser_length_m
        mid = L / 2.0
        views = [("three_quarter", L + 9.0, 6.5, 2.6, (L - 4.0, 0.0, 1.2)),
                 ("side", -8.0, 10.0, 2.0, (mid, 0.0, 0.8)),
                 ("close_risers", builder.scene.diffuser_margin_m, 2.6, 1.4,
                  (builder.scene.diffuser_margin_m, 0.0, 1.4))]
        lum = {}
        imgs = []
        for name, s, t, h, look in views:
            px, py = builder.to_world(s, t)
            pz = builder.bed(s, t) + h
            lxw, lyw = builder.to_world(look[0], look[1])
            lzw = builder.bed(look[0], look[1]) + look[2]
            vyaw = math.degrees(math.atan2(lyw - py, lxw - px))
            dist = math.hypot(lxw - px, lyw - py)
            vpitch = -math.degrees(math.atan2(pz - lzw, max(dist, 1e-3)))
            state, _ = hold([px, py, pz], vyaw, pitch=vpitch, ticks=40)
            rgb = np.asarray(state["RGBCamera"])[:, :, :3][:, :, ::-1]
            plt.imsave(out / f"{tag}_{name}.png", rgb.astype(np.uint8))
            lum[name] = round(float(rgb.mean()), 1)
            imgs.append((name, rgb))
        # viewport plan view
        pxc, pyc = builder.to_world(mid, -15.0)
        env.move_viewport([pxc, pyc, bed0 + 26.0], [0.0, -60.0, 90.0])
        state = None
        for _ in range(12):
            state = env.tick()
        vp = np.asarray(state["ViewportCapture"])[:, :, :3][:, :, ::-1]
        plt.imsave(out / f"{tag}_plan.png", vp.astype(np.uint8))
        imgs.append(("plan", vp))
        site_info["luminance"] = lum

        fig, axes = plt.subplots(1, len(imgs), figsize=(5.5 * len(imgs), 3.5))
        for ax, (name, im) in zip(np.atleast_1d(axes), imgs):
            ax.imshow(im)
            ax.set_title(f"{args.world} {tag} {name}", fontsize=8)
            ax.axis("off")
        fig.tight_layout()
        fig.savefig(out / f"{tag}_sheet.png", dpi=110)
        plt.close(fig)

        # optional sonar clutter (with the structure present it measures
        # structure+clutter on the official engine the structure is octree-
        # invisible, so frames = NATIVE CLUTTER ONLY)
        if args.sonar:
            cx, cy = builder.to_world(mid, 0.0)
            clut = {}
            for bear in (0.0, 90.0):
                b = math.radians(bear)
                px, py = cx + 18 * math.cos(b), cy + 18 * math.sin(b)
                vyaw = math.degrees(math.atan2(cy - py, cx - px))
                _, frame = hold([px, py, bed0 + 3.0], vyaw, sonar_grab=True)
                if frame is None:
                    clut[f"b{int(bear)}"] = None
                    continue
                nz = frame[frame > 0]
                clut[f"b{int(bear)}"] = {
                    "nonzero_frac": round(float((frame > 0).mean()), 4),
                    "mean": round(float(frame.mean()), 6),
                    "p99": round(float(np.percentile(frame, 99)), 5),
                    "nonzero_mean": round(float(nz.mean()), 5) if nz.size else 0.0,
                }
                np.savez_compressed(out / f"{tag}_clutter_b{int(bear)}.npz",
                                    frame=frame)
            site_info["native_clutter"] = clut
        report["sites"].append(site_info)
        print(f"[eval] {tag}: bed {bed0:.1f}, relief {relief:.2f} m, "
              f"lum {lum}")

    (out / "report.json").write_text(json.dumps(report, indent=2),
                                     encoding="utf-8")
    print(f"[eval] DONE -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

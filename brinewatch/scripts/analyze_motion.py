"""Motion-quality feedback for a completed mission run.

Reads a run directory (outputs/<run>/) and reports:
- distance travelled, mean/median speed, time span;
- stationary fraction (5 s windows with < 0.25 m of movement);
- zig-zag: distribution of heading changes over 10 s windows;
- straightness index (net displacement / path length per 60 s window);
- stalls and collisions from mission_log.jsonl.

Usage:
    python scripts/analyze_motion.py outputs/<run_dir>
    python scripts/analyze_motion.py            # newest run under outputs/
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]


def newest_run_dir() -> Path:
    runs = sorted((REPO_ROOT / "outputs").glob("*/"), key=lambda p: p.name)
    if not runs:
        raise SystemExit("no runs under outputs/")
    return runs[-1]


def main() -> int:
    run_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else newest_run_dir()
    npz_path = run_dir / "plume_maps.npz"
    log_path = run_dir / "mission_log.jsonl"
    if not npz_path.exists():
        raise SystemExit(f"{npz_path} not found (mission incomplete?)")

    data = np.load(npz_path)
    if "trajectory" not in data:
        raise SystemExit("this run predates trajectory logging; re-run the mission")
    traj = data["trajectory"]  # (N, 4): t, x, y, z
    t, x, y, z = traj[:, 0], traj[:, 1], traj[:, 2], traj[:, 3]

    print(f"=== Motion report: {run_dir.name} ===")
    steps = np.diff(traj[:, 1:4], axis=0)
    seg = np.linalg.norm(steps, axis=1)
    dt = np.diff(t)
    ok = dt > 1e-6
    speed = seg[ok] / dt[ok]
    print(f"samples: {len(traj)}  time span: {t[-1] - t[0]:.0f} s  "
          f"distance: {seg.sum():.0f} m")
    print(f"speed: mean {speed.mean():.2f} m/s  median {np.median(speed):.2f} m/s  "
          f"p95 {np.percentile(speed, 95):.2f} m/s")

    # --- stationary fraction: 5 s windows moving < 0.25 m ------------------ #
    win = 5.0
    edges = np.arange(t[0], t[-1], win)
    idx = np.searchsorted(t, edges)
    moved = []
    for a, b in zip(idx[:-1], idx[1:]):
        if b > a:
            d = float(np.linalg.norm(traj[min(b, len(traj) - 1), 1:4] - traj[a, 1:4]))
            moved.append(d)
    moved = np.asarray(moved)
    stationary = float(np.mean(moved < 0.25)) if moved.size else float("nan")
    print(f"stationary fraction (5 s windows < 0.25 m): {stationary:.1%}"
          + ("  <-- CHECK: vehicle idles too much" if stationary > 0.15 else "  (ok)"))

    # --- zig-zag: heading change over 10 s windows ------------------------- #
    win = 10.0
    hs, ts = [], []
    edges = np.arange(t[0], t[-1], win)
    idx = np.searchsorted(t, edges)
    for a, b in zip(idx[:-1], idx[1:]):
        b = min(b, len(traj) - 1)
        dx, dy = x[b] - x[a], y[b] - y[a]
        if math.hypot(dx, dy) > 1.0:
            hs.append(math.atan2(dy, dx))
            ts.append(0.5 * (t[a] + t[b]))
    turns = np.abs(np.degrees(np.arctan2(np.sin(np.diff(hs)), np.cos(np.diff(hs)))))
    if turns.size:
        sharp = float(np.mean(turns > 90.0))
        print(f"heading change per 10 s: median {np.median(turns):.0f} deg  "
              f"p90 {np.percentile(turns, 90):.0f} deg  "
              f"U-turnish (>90 deg): {sharp:.1%}"
              + ("  <-- CHECK: very zig-zag" if sharp > 0.35 else "  (ok)"))

    # --- straightness over 60 s ------------------------------------------- #
    win = 60.0
    edges = np.arange(t[0], t[-1], win)
    idx = np.searchsorted(t, edges)
    ratios = []
    for a, b in zip(idx[:-1], idx[1:]):
        b = min(b, len(traj) - 1)
        path = float(np.sum(seg[a:b]))
        net = float(np.linalg.norm(traj[b, 1:4] - traj[a, 1:4]))
        if path > 1.0:
            ratios.append(net / path)
    if ratios:
        print(f"straightness (net/path per 60 s): mean {np.mean(ratios):.2f} "
              f"(1.0 = straight line; lawnmower legs ~0.9, adaptive ~0.5-0.8)")

    # --- events from the log ----------------------------------------------- #
    stalls, collisions = 0, 0
    if log_path.exists():
        for line in log_path.read_text(encoding="utf-8").splitlines():
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("kind") == "navigation_stalled":
                stalls += 1
            elif ev.get("kind") == "collision":
                collisions = max(collisions, int(ev.get("count", 0)))
    print(f"stalled legs: {stalls}" + ("  <-- CHECK" if stalls > 3 else "  (ok)"))
    print(f"collision events: {collisions}" + ("  <-- CHECK" if collisions > 2 else "  (ok)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

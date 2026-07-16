"""Offline detector evaluation and gate tuning on a recorded sonar mission.

Replays a mission's sonar recording (no simulator needed), runs the detector
with permissive gates, and separates contacts into TARGET (world estimate
within ``--target-radius`` of the known structure position) and CLUTTER.
Ground truth is used ONLY here, offline, for evaluation — never online.

Outputs (into <recording>/../detector_eval/ and the application assets dir):
- strength/area distributions for target vs clutter contacts;
- precision/recall vs strength-gate curve;
- localization error of the consensus estimate with the tuned localizer;
- example frames: detection overlay + hardest clutter example;
- recommended gate values (JSON).

Usage:
    python scripts/evaluate_sonar_detector.py --recording outputs/<run>/sonar_recording \
        --target-x 456.5 --target-y -630.5
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from brinewatch.perception.sonar_diffuser_detector import (
    DetectorConfig,
    SonarDiffuserDetector,
)
from brinewatch.perception.sonar_localizer import (
    SonarDiffuserLocator,
    SonarLocalizerConfig,
)
from brinewatch.sensors.sonar_recorder import SonarReplay


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--recording", type=str, required=True)
    ap.add_argument("--target-x", type=float, required=True)
    ap.add_argument("--target-y", type=float, required=True)
    ap.add_argument("--target-radius", type=float, default=8.0)
    ap.add_argument("--prior-x", type=float, default=None)
    ap.add_argument("--prior-y", type=float, default=None)
    ap.add_argument("--assets", type=str, default=str(
        REPO_ROOT / "docs" / "application" / "pfh2026" / "assets" / "sonar"))
    args = ap.parse_args()

    replay = SonarReplay(args.recording)
    out = Path(args.recording).parent / "detector_eval"
    out.mkdir(parents=True, exist_ok=True)
    assets = Path(args.assets)
    assets.mkdir(parents=True, exist_ok=True)

    # ---- pass 1: permissive detection, classify contacts offline ---------- #
    det = SonarDiffuserDetector(DetectorConfig(z_threshold=4.5, min_area_bins=12,
                                               max_contacts=6, min_range_m=8.0))
    target = np.array([args.target_x, args.target_y])
    rows = []
    frames = list(replay)
    for idx, frame in enumerate(frames):
        for c in det.detect(frame):
            yaw = frame.vehicle_rpy[2]
            ex = frame.vehicle_xyz[0] + c.range_m * math.cos(yaw + c.bearing_rad)
            ey = frame.vehicle_xyz[1] + c.range_m * math.sin(yaw + c.bearing_rad)
            d_target = float(np.hypot(ex - target[0], ey - target[1]))
            rows.append({
                "frame": idx, "strength": c.strength, "area": c.area_bins,
                "range_m": c.range_m, "est_x": ex, "est_y": ey,
                "is_target": d_target <= args.target_radius,
                "d_target": d_target,
            })
    n_t = sum(1 for r in rows if r["is_target"])
    n_c = len(rows) - n_t
    print(f"[eval] {len(frames)} frames, {len(rows)} raw contacts "
          f"({n_t} target / {n_c} clutter)")
    if n_t == 0:
        print("[eval] WARNING: no target contacts in this recording — the "
              "vehicle may never have insonified the structure. Gate tuning "
              "will be clutter-rejection only.")

    ts = np.array([r["strength"] for r in rows if r["is_target"]])
    cs = np.array([r["strength"] for r in rows if not r["is_target"]])
    stats = {
        "n_frames": len(frames),
        "n_target_contacts": int(n_t),
        "n_clutter_contacts": int(n_c),
        "target_strength_p10_p50_p90": ([float(np.percentile(ts, q)) for q in (10, 50, 90)]
                                        if n_t else None),
        "clutter_strength_p50_p90_p99": ([float(np.percentile(cs, q)) for q in (50, 90, 99)]
                                         if n_c else None),
    }

    # ---- precision/recall vs strength gate ------------------------------- #
    gates = np.arange(5.0, 260.0, 5.0)
    pr = []
    for g in gates:
        tp = sum(1 for r in rows if r["is_target"] and r["strength"] >= g)
        fp = sum(1 for r in rows if not r["is_target"] and r["strength"] >= g)
        fn = sum(1 for r in rows if r["is_target"] and r["strength"] < g)
        precision = tp / (tp + fp) if tp + fp else 1.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        pr.append({"gate": float(g), "precision": precision, "recall": recall,
                   "tp": tp, "fp": fp})
    # Recommended gate: highest recall subject to precision >= 0.9
    good = [p for p in pr if p["precision"] >= 0.9 and p["recall"] > 0]
    recommended = min(good, key=lambda p: p["gate"]) if good else None
    stats["recommended_min_strength"] = recommended["gate"] if recommended else None
    stats["recommended_pr"] = recommended

    # ---- localizer replay with tuned gates -------------------------------- #
    loc_err = None
    if recommended:
        prior = ((args.prior_x, args.prior_y)
                 if args.prior_x is not None and args.prior_y is not None else None)
        loc = SonarDiffuserLocator(SonarLocalizerConfig(
            detector=DetectorConfig(min_range_m=8.0),
            min_strength=recommended["gate"],
            prior_xy=prior, prior_gate_m=30.0))
        detections = 0
        for frame in frames:
            if loc.update(frame) is not None:
                detections += 1
        if loc.consensus is not None:
            loc_err = float(np.hypot(loc.consensus[0] - target[0],
                                     loc.consensus[1] - target[1]))
        stats["replay_detections_emitted"] = detections
        stats["replay_consensus"] = loc.consensus
        stats["replay_localization_error_m"] = loc_err
        print(f"[eval] tuned replay: {detections} detections, consensus "
              f"{loc.consensus}, error {loc_err}")

    # ---- plots ------------------------------------------------------------ #
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), constrained_layout=True)
    bins = np.linspace(0, max(260.0, (ts.max() if n_t else 0) + 10), 40)
    if n_c:
        axes[0].hist(cs, bins=bins, alpha=0.65, label=f"clutter (n={n_c})", color="C7")
    if n_t:
        axes[0].hist(ts, bins=bins, alpha=0.75, label=f"structure (n={n_t})", color="C2")
    if recommended:
        axes[0].axvline(recommended["gate"], color="crimson", linestyle="--",
                        label=f"gate = {recommended['gate']:.0f}")
    axes[0].set_xlabel("Contact strength (robust z units)")
    axes[0].set_ylabel("Contacts")
    axes[0].set_title("Structure vs clutter — recorded mission frames")
    axes[0].legend()
    axes[1].plot([p["recall"] for p in pr], [p["precision"] for p in pr], "o-",
                 markersize=3)
    if recommended:
        axes[1].plot(recommended["recall"], recommended["precision"], "r*",
                     markersize=14)
    axes[1].set_xlabel("Recall")
    axes[1].set_ylabel("Precision")
    axes[1].set_title("Precision-recall vs strength gate")
    axes[1].grid(alpha=0.3)
    fig.savefig(out / "detector_eval.png", dpi=140)
    fig.savefig(assets / "detector_eval.png", dpi=140)
    plt.close(fig)

    (out / "detector_eval.json").write_text(json.dumps(stats, indent=2),
                                            encoding="utf-8")
    (assets / "detector_eval.json").write_text(json.dumps(stats, indent=2),
                                               encoding="utf-8")
    print(json.dumps(stats, indent=2))
    print(f"[eval] outputs: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

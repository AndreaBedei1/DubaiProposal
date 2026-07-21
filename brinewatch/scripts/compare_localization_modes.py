"""Compare the two sonar-localization modes on the SAME recorded engine data.

  * background subtraction  (pre-installation baseline; historical mode)
  * in-situ single mission   (no baseline; chart + geometry + persistence)

Both consume the committed recorded frames in outputs/localization/v2_run1/
(one live orbit acquisition over the spawned outfall + a structure-free
background pass at the same poses). We report, for each mode:

  - estimate + error to the true diffuser centre (truth used ONLY for scoring),
  - fallback (did it produce an estimate at all),
  - a clutter-sensitivity sweep: synthetic speckle + bright false blobs are
    added to the LIVE frames at increasing levels and both modes re-run.

The in-situ mode additionally reports a bootstrap uncertainty; we check whether
the truth lies within its stated 1-sigma / 2-sigma radius (calibration).

    python scripts/compare_localization_modes.py \
        --data outputs/localization/v2_run1 --out outputs/localization/compare
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from brinewatch.perception.insitu_locator import (          # noqa: E402
    InSituDiffuserLocator, InSituLocatorConfig)
from brinewatch.perception.sonar_background_locator import (  # noqa: E402
    BackgroundLocatorConfig, SonarBackgroundLocator)
from brinewatch.perception.sonar_diffuser_detector import DetectorConfig  # noqa: E402
from brinewatch.sensors.sonar_types import SonarFrame        # noqa: E402

SONAR = {"rmin": 1.0, "rmax": 40.0, "az": 120.0, "elev": 20.0}
# chart prior: design intent, deliberately offset from the as-built truth to
# exercise the gates (NOT ground truth; truth is (39.8, 0) from site.json).
PRIOR_XY = (44.0, 5.0)
PRIOR_AXIS_DEG = 0.0


def frame_of(img, meta):
    return SonarFrame(t=0.0, image=np.asarray(img, dtype=np.float32),
                      range_min_m=SONAR["rmin"], range_max_m=SONAR["rmax"],
                      azimuth_fov_deg=SONAR["az"], elevation_fov_deg=SONAR["elev"],
                      vehicle_xyz=tuple(meta["actual_xyz"][:3]),
                      vehicle_rpy=(0.0, 0.0, meta["yaw_rad"]))


def add_clutter(img, level, rng):
    """Speckle + a few bright false blobs, scaled by ``level`` (0 = none)."""
    if level <= 0:
        return img
    out = np.asarray(img, dtype=np.float32).copy()
    scale = float(np.nanpercentile(out, 99) + 1e-3)
    out += rng.random(out.shape).astype(np.float32) * 0.15 * level * scale
    nr, nc = out.shape
    for _ in range(2 * level):
        r = rng.integers(int(0.15 * nr), nr)         # not in the near field
        c = rng.integers(0, nc)
        r0, c0 = max(0, r - 3), max(0, c - 3)
        out[r0:r0 + 6, c0:c0 + 6] += 1.5 * scale
    return out


def insitu_estimate(live_frames, seed=0):
    cfg = InSituLocatorConfig(
        detector=DetectorConfig(min_range_m=6.0, z_threshold=3.5, min_area_bins=8),
        prior_xy=PRIOR_XY, prior_gate_m=30.0, prior_axis_deg=PRIOR_AXIS_DEG,
        corridor_halfwidth_m=20.0, line_inlier_m=4.0, min_inliers=6,
        min_aspect_span_deg=25.0, bootstrap=200)
    loc = InSituDiffuserLocator(cfg, seed=seed)
    loc.ingest_all(live_frames)
    return loc.localize()


def run(args) -> int:
    data = Path(args.data)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    site = json.loads((data / "site.json").read_text(encoding="utf-8"))
    cx, cy = site["true_diffuser_centre"]

    bg = dict(np.load(data / "frames_background.npz"))
    acq_files = sorted(data.glob("frames_acq_*.npz"))
    if not acq_files:
        print("[compare] no acquisitions in", data)
        return 1
    acq_path = acq_files[0]
    tag = acq_path.stem.replace("frames_", "")
    frames_raw = dict(np.load(acq_path))
    meta = json.loads((data / f"meta_{tag}.json").read_text(encoding="utf-8"))
    keys = [k for k in frames_raw if k in bg and k in meta]
    print(f"[compare] acquisition {tag}: {len(keys)} pose-matched frames")

    def err(est):
        return None if est is None else round(math.hypot(est[0] - cx, est[1] - cy), 2)

    levels = [0, 1, 2, 3]
    sweep = []
    for level in levels:
        rng = np.random.default_rng(1000 + level)
        live_frames = []
        insitu_bg = SonarBackgroundLocator(BackgroundLocatorConfig(
            detector=DetectorConfig(min_range_m=6.0, z_threshold=3.5, min_area_bins=8),
            prior_xy=PRIOR_XY, prior_gate_m=30.0, min_contacts_for_consensus=5))
        for k in keys:
            live_img = add_clutter(frames_raw[k], level, rng)
            live_frames.append(frame_of(live_img, meta[k]))
            insitu_bg.ingest(frame_of(bg[k], meta[k]), frame_of(live_img, meta[k]))
        r_in = insitu_estimate(live_frames, seed=7)
        r_bg = insitu_bg.localize()
        row = {
            "clutter_level": level,
            "insitu": {"estimate": (None if r_in.fallback else
                                    [round(r_in.estimate[0], 2), round(r_in.estimate[1], 2)]),
                       "error_m": err(None if r_in.fallback else r_in.estimate),
                       "fallback": r_in.fallback,
                       "sigma_radius_m": r_in.sigma_radius_m,
                       "n_inliers": r_in.n_inliers,
                       "aspect_span_deg": r_in.aspect_span_deg,
                       "axis_deg": r_in.axis_deg},
            "background": {"estimate": (None if r_bg.fallback else
                                        [round(r_bg.estimate[0], 2), round(r_bg.estimate[1], 2)]),
                           "error_m": err(None if r_bg.fallback else r_bg.estimate),
                           "fallback": r_bg.fallback,
                           "n_contacts": r_bg.n_contacts},
        }
        # uncertainty calibration for the in-situ estimate
        if not r_in.fallback and r_in.sigma_radius_m > 0:
            e = err(r_in.estimate)
            row["insitu"]["truth_within_1sigma"] = bool(e <= r_in.sigma_radius_m)
            row["insitu"]["truth_within_2sigma"] = bool(e <= 2 * r_in.sigma_radius_m)
        sweep.append(row)
        print(f"[compare] clutter {level}: in-situ err "
              f"{row['insitu']['error_m']} (sig {r_in.sigma_radius_m}) | "
              f"background err {row['background']['error_m']}")

    summary = {
        "acquisition": tag,
        "true_diffuser_centre": [cx, cy],
        "chart_prior_xy": list(PRIOR_XY),
        "prior_axis_deg": PRIOR_AXIS_DEG,
        "modes": {
            "background": "pre-installation baseline subtraction (historical; "
                          "needs a structure-free pass at the same poses)",
            "insitu": "single inspection pass, no baseline; chart prior + "
                      "diffuser-line RANSAC + multi-aspect persistence + "
                      "bootstrap uncertainty",
        },
        "clutter_sweep": sweep,
        "clean_result": {
            "insitu_error_m": sweep[0]["insitu"]["error_m"],
            "insitu_sigma_radius_m": sweep[0]["insitu"]["sigma_radius_m"],
            "background_error_m": sweep[0]["background"]["error_m"],
        },
        "note": ("truth used ONLY for scoring; both modes run on the identical "
                 "committed recorded frames; clutter is synthetic speckle + "
                 "false blobs added to the LIVE frames"),
    }
    (out / "comparison.json").write_text(json.dumps(summary, indent=2),
                                         encoding="utf-8")
    _plot(sweep, summary, out / "comparison.png")
    print(f"[compare] DONE -> {out}")
    print(json.dumps(summary["clean_result"], indent=2))
    return 0


def _plot(sweep, summary, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    lv = [r["clutter_level"] for r in sweep]
    ei = [r["insitu"]["error_m"] for r in sweep]
    si = [r["insitu"]["sigma_radius_m"] for r in sweep]
    eb = [r["background"]["error_m"] for r in sweep]

    def clean(vals):
        return [np.nan if v is None else v for v in vals]

    fig, ax = plt.subplots(1, 2, figsize=(13, 5), constrained_layout=True)
    ax[0].errorbar(lv, clean(ei), yerr=clean(si), marker="o", capsize=4,
                   color="tab:blue", label="in-situ (1σ bars)")
    ax[0].plot(lv, clean(eb), marker="s", color="tab:orange",
               label="background subtraction")
    ax[0].set_xlabel("synthetic clutter level")
    ax[0].set_ylabel("localization error to true centre (m)")
    ax[0].set_title("Clutter sensitivity")
    ax[0].set_xticks(lv)
    ax[0].grid(alpha=0.3)
    ax[0].legend()

    # map view at clutter level 0
    cx, cy = summary["true_diffuser_centre"]
    px, py = summary["chart_prior_xy"]
    ax[1].plot(cx, cy, "k*", ms=16, label="true centre")
    ax[1].plot(px, py, "x", color="grey", ms=10, label="chart prior")
    r0 = sweep[0]
    if r0["insitu"]["estimate"]:
        ex, ey = r0["insitu"]["estimate"]
        sig = r0["insitu"]["sigma_radius_m"]
        ax[1].plot(ex, ey, "o", color="tab:blue", ms=9, label="in-situ est.")
        th = np.linspace(0, 2 * math.pi, 60)
        ax[1].plot(ex + sig * np.cos(th), ey + sig * np.sin(th), "-",
                   color="tab:blue", alpha=0.5, lw=1)
    if r0["background"]["estimate"]:
        bx, by = r0["background"]["estimate"]
        ax[1].plot(bx, by, "s", color="tab:orange", ms=9, label="background est.")
    ax[1].set_aspect("equal", "datalim")
    ax[1].set_xlabel("x (m)")
    ax[1].set_ylabel("y (m)")
    ax[1].set_title("Estimates vs truth (clutter 0)")
    ax[1].grid(alpha=0.3)
    ax[1].legend(loc="best", fontsize=9)
    fig.suptitle("Sonar localization: in-situ vs background subtraction "
                 f"({summary['acquisition']})", fontsize=13)
    fig.savefig(path, dpi=120)
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", default=str(REPO / "outputs" / "localization" / "v2_run1"))
    ap.add_argument("--out", default=str(REPO / "outputs" / "localization" / "compare"))
    args = ap.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())

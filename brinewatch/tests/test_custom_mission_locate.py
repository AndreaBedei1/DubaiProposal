"""Integration test of the custom-mission LOCATE pipeline on REAL recorded
custom-engine sonar frames (committed in outputs/localization/v2_run1/).

Exercises exactly what run_custom_holoocean_mission.py does at LOCATE:
background subtraction (baseline vs inspection at the same poses) + the in-situ
diffuser-LINE fit. Engine-free (uses recorded frames), so it runs in CI, but it
validates the real localization code path end-to-end on genuine engine data.
Skipped cleanly if the recorded evidence is not present.
"""
import json
import math
from pathlib import Path

import numpy as np
import pytest

from brinewatch.perception.insitu_locator import (
    InSituDiffuserLocator, InSituLocatorConfig)
from brinewatch.perception.sonar_diffuser_detector import DetectorConfig
from brinewatch.sensors.sonar_types import SonarFrame

DATA = Path(__file__).resolve().parents[1] / "outputs" / "localization" / "v2_run1"
SON = {"rmin": 1.0, "rmax": 40.0, "az": 120.0, "elev": 20.0}

pytestmark = pytest.mark.skipif(
    not (DATA / "frames_background.npz").is_file(),
    reason="recorded custom-engine frames not present")


def _frame(img, meta_entry):
    return SonarFrame(
        t=0.0, image=np.asarray(img, np.float32),
        range_min_m=SON["rmin"], range_max_m=SON["rmax"],
        azimuth_fov_deg=SON["az"], elevation_fov_deg=SON["elev"],
        vehicle_xyz=tuple(meta_entry["actual_xyz"][:3]),
        vehicle_rpy=(0.0, 0.0, float(meta_entry["yaw_rad"])))


def test_custom_locate_pipeline_on_recorded_frames():
    site = json.loads((DATA / "site.json").read_text(encoding="utf-8"))
    cx, cy = site["true_diffuser_centre"]                    # (39.8, 0), scoring only
    bg = dict(np.load(DATA / "frames_background.npz"))
    acq_files = sorted(DATA.glob("frames_acq_*.npz"))
    assert acq_files, "no acquisition frames committed"
    tag = acq_files[0].stem.replace("frames_", "")
    frames = dict(np.load(acq_files[0]))
    meta = json.loads((DATA / f"meta_{tag}.json").read_text(encoding="utf-8"))

    # chart prior deliberately offset from truth (as in the mission)
    loc = InSituDiffuserLocator(InSituLocatorConfig(
        detector=DetectorConfig(min_range_m=6.0, z_threshold=3.5, min_area_bins=8),
        prior_xy=(42.0, 2.0), prior_gate_m=30.0, prior_axis_deg=0.0,
        corridor_halfwidth_m=12.0, line_inlier_m=4.0, min_inliers=6,
        min_aspect_span_deg=25.0, bootstrap=100), seed=7)

    used = 0
    for key in sorted(set(bg) & set(frames) & set(meta)):
        res = np.clip(frames[key].astype(np.float32) - bg[key].astype(np.float32),
                      0.0, None)
        loc.ingest(_frame(res, meta[key]))
        used += 1
    assert used >= 8, f"too few pose-matched frames ({used})"

    r = loc.localize()
    assert not r.fallback, r.reason
    err = math.hypot(r.estimate[0] - cx, r.estimate[1] - cy)
    # single-radius recorded ring: the diffuser-line fit should land within a
    # survey-box-scale distance of the true centre (not the 25 m off-axis rock)
    assert err < 9.0, f"localization error {err:.1f} m too large (est {r.estimate})"
    assert r.sigma_radius_m > 0.0                            # uncertainty reported
    # the fitted axis is roughly along the diffuser (x-axis, 0 deg)
    assert abs(((r.axis_deg + 90) % 180) - 90) < 35.0

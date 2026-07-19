"""Engine-free tests for the background-subtraction sonar localizer.

Synthetic sonar frames: a flat 'clutter' background plus, in the live frame,
a bright compact return at a known range/bearing from each pose. The locator
must recover the world position of that return within a couple of metres and
report no fallback; with the SAME frame as background and live (no structure),
it must fall back.
"""
import math

import numpy as np

from brinewatch.perception.sonar_background_locator import (
    BackgroundLocatorConfig,
    SonarBackgroundLocator,
)
from brinewatch.sensors.sonar_types import SonarFrame

RMIN, RMAX, AZ, ELEV = 1.0, 40.0, 120.0, 20.0
NR, NA = 512, 256


def make_frame(pose_xyz, yaw_rad, target_xy=None, clutter_seed=0):
    """A frame with random clutter; if target_xy given, add a bright blob at
    the range/bearing of that world point (within FOV)."""
    rng = np.random.default_rng(clutter_seed)
    img = rng.uniform(0.0, 0.05, size=(NR, NA)).astype(np.float32)  # weak clutter
    fr = SonarFrame(t=0.0, image=img, range_min_m=RMIN, range_max_m=RMAX,
                    azimuth_fov_deg=AZ, elevation_fov_deg=ELEV,
                    vehicle_xyz=tuple(pose_xyz), vehicle_rpy=(0.0, 0.0, yaw_rad))
    if target_xy is not None:
        dx = target_xy[0] - pose_xyz[0]
        dy = target_xy[1] - pose_xyz[1]
        rng_m = math.hypot(dx, dy)
        world_bearing = math.atan2(dy, dx)
        rel = world_bearing - yaw_rad
        rel = (rel + math.pi) % (2 * math.pi) - math.pi
        if abs(math.degrees(rel)) <= AZ / 2 and RMIN < rng_m < RMAX:
            row = int((rng_m - RMIN) / (RMAX - RMIN) * (NR - 1))
            # bearing_of_col: frac=(col+0.5)/NA, bearing = (0.5-frac)*AZ  (deg)
            frac = 0.5 - math.degrees(rel) / AZ
            col = int(frac * NA - 0.5)
            r0, r1 = max(0, row - 6), min(NR, row + 6)
            c0, c1 = max(0, col - 4), min(NA, col + 4)
            img[r0:r1, c0:c1] = 3.0  # bright compact blob
    return fr


def test_background_subtraction_recovers_target():
    target = (40.0, 0.0)
    cfg = BackgroundLocatorConfig(prior_xy=(45.0, 8.0), prior_gate_m=30.0)
    loc = SonarBackgroundLocator(cfg)
    # 12 poses on a ring around the target
    for k in range(12):
        a = 2 * math.pi * k / 12
        px, py = target[0] + 18 * math.cos(a), target[1] + 18 * math.sin(a)
        yaw = math.atan2(target[1] - py, target[0] - px)
        bg = make_frame((px, py, -70), yaw, target_xy=None, clutter_seed=k)
        live = make_frame((px, py, -70), yaw, target_xy=target, clutter_seed=k)
        loc.ingest(bg, live)
    res = loc.localize()
    assert not res.fallback
    assert res.estimate is not None
    err = math.hypot(res.estimate[0] - target[0], res.estimate[1] - target[1])
    assert err < 3.0, (res.estimate, err)
    assert res.aspect_span_deg > 90.0  # ring gives broad aspect diversity


def test_no_structure_falls_back():
    cfg = BackgroundLocatorConfig(prior_xy=(45.0, 8.0))
    loc = SonarBackgroundLocator(cfg)
    for k in range(12):
        a = 2 * math.pi * k / 12
        px, py = 40 + 18 * math.cos(a), 18 * math.sin(a)
        yaw = math.atan2(-py, 40 - px)
        # identical background and live -> zero residual -> no contacts
        f = make_frame((px, py, -70), yaw, target_xy=None, clutter_seed=k)
        loc.ingest(f, f)
    res = loc.localize()
    assert res.fallback
    assert res.estimate is None


def test_prior_gate_rejects_far_contacts():
    target = (40.0, 0.0)
    # prior far from the target -> all residual contacts gated out -> fallback
    cfg = BackgroundLocatorConfig(prior_xy=(-100.0, -100.0), prior_gate_m=10.0)
    loc = SonarBackgroundLocator(cfg)
    for k in range(12):
        a = 2 * math.pi * k / 12
        px, py = target[0] + 18 * math.cos(a), target[1] + 18 * math.sin(a)
        yaw = math.atan2(target[1] - py, target[0] - px)
        bg = make_frame((px, py, -70), yaw, target_xy=None, clutter_seed=k)
        live = make_frame((px, py, -70), yaw, target_xy=target, clutter_seed=k)
        loc.ingest(bg, live)
    assert loc.localize().fallback

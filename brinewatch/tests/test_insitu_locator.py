"""Engine-free tests for the in-situ (single-mission) sonar localizer.

Synthetic range-azimuth frames are built with a bright compact blob at a known
world position; the locator must recover the centre from multi-aspect views,
reject off-chart clutter, fit the diffuser axis and fall back when starved.
"""
import math

import numpy as np
import pytest

from brinewatch.perception.insitu_locator import (
    InSituDiffuserLocator, InSituLocatorConfig, _aspect_span_deg,
)
from brinewatch.sensors.sonar_types import SonarFrame

RMIN, RMAX, AZ, ELEV = 1.0, 40.0, 120.0, 20.0
NR, NA = 512, 256


def synth_frame(targets, vehicle_xy, yaw_rad, bed_z=-50.0, noise=0.02, seed=0):
    """A frame from ``vehicle_xy`` at heading ``yaw_rad`` that images each world
    target in ``targets`` as a bright 4x4 blob (if in range and FOV)."""
    rng = np.random.default_rng(seed)
    img = rng.random((NR, NA)).astype(np.float32) * noise
    vx, vy = vehicle_xy
    for (tx, ty) in targets:
        rng_m = math.hypot(tx - vx, ty - vy)
        if not (RMIN + 2.0 < rng_m < RMAX - 2.0):
            continue
        bearing = math.atan2(ty - vy, tx - vx) - yaw_rad
        bearing = math.atan2(math.sin(bearing), math.cos(bearing))
        if abs(math.degrees(bearing)) > AZ / 2.0 - 3.0:
            continue
        row = int((rng_m - RMIN) / (RMAX - RMIN) * NR - 0.5)
        frac = 0.5 - math.degrees(bearing) / AZ
        col = int(frac * NA - 0.5)
        r0, c0 = max(0, row - 2), max(0, col - 2)
        img[r0:r0 + 4, c0:c0 + 4] = 6.0
    return SonarFrame(t=0.0, image=img, range_min_m=RMIN, range_max_m=RMAX,
                      azimuth_fov_deg=AZ, elevation_fov_deg=ELEV,
                      vehicle_xyz=(vx, vy, bed_z + 3.0),
                      vehicle_rpy=(0.0, 0.0, yaw_rad))


def orbit_frames(targets, centre, radius=16.0, n=12, seed0=0):
    """Frames from ``n`` headings orbiting ``centre``, each pointed inward."""
    frames = []
    cx, cy = centre
    for k in range(n):
        b = 2 * math.pi * k / n
        px, py = cx + radius * math.cos(b), cy + radius * math.sin(b)
        yaw = math.atan2(cy - py, cx - px)
        frames.append(synth_frame(targets, (px, py), yaw, seed=seed0 + k))
    return frames


def _cfg(**kw):
    base = dict(prior_xy=(40.0, 0.0), prior_gate_m=30.0, min_inliers=5,
                min_aspect_span_deg=25.0, bootstrap=80)
    base.update(kw)
    return InSituLocatorConfig(**base)


def test_recovers_centre_from_multi_aspect():
    target = (40.0, 0.0)
    loc = InSituDiffuserLocator(_cfg(), seed=1)
    loc.ingest_all(orbit_frames([target], target, n=12))
    r = loc.localize()
    assert not r.fallback, r.reason
    assert math.hypot(r.estimate[0] - 40.0, r.estimate[1] - 0.0) < 3.0
    assert r.aspect_span_deg > 120.0        # orbited all the way around
    assert r.sigma_radius_m > 0.0           # uncertainty is quantified
    assert r.n_inliers >= 5


def test_rejects_off_chart_clutter():
    target = (40.0, 0.0)
    clutter = (40.0, 70.0)                  # far outside the 30 m prior gate
    loc = InSituDiffuserLocator(_cfg(), seed=2)
    loc.ingest_all(orbit_frames([target, clutter], target, n=12))
    r = loc.localize()
    assert not r.fallback, r.reason
    # estimate stays on the true target, unmoved by the clutter
    assert math.hypot(r.estimate[0] - 40.0, r.estimate[1] - 0.0) < 3.0


def test_recovers_diffuser_axis_orientation():
    # three collinear targets along x (the diffuser line)
    targets = [(34.0, 0.0), (40.0, 0.0), (46.0, 0.0)]
    loc = InSituDiffuserLocator(_cfg(line_inlier_m=3.0), seed=3)
    loc.ingest_all(orbit_frames(targets, (40.0, 0.0), radius=20.0, n=16))
    r = loc.localize()
    assert not r.fallback, r.reason
    assert abs(r.axis_deg) < 20.0 or abs(abs(r.axis_deg) - 180.0) < 20.0
    assert r.along_track_extent_m > r.across_track_rms_m   # elongated, as a diffuser
    assert math.hypot(r.estimate[0] - 40.0, r.estimate[1]) < 4.0


def test_fallback_when_starved():
    loc = InSituDiffuserLocator(_cfg(), seed=4)
    loc.ingest_all(orbit_frames([(40.0, 0.0)], (40.0, 0.0), n=2))
    r = loc.localize()
    assert r.fallback
    assert r.estimate is None


def test_aspect_span_wraparound():
    # headings clustered near 0 and near 2pi are a NARROW span, not wide
    h = np.array([0.05, -0.05, 0.1, 6.23])   # ~ +/-6 deg around 0
    assert _aspect_span_deg(h) < 30.0
    # a full sweep is ~360 deg
    full = np.linspace(0, 2 * math.pi, 12, endpoint=False)
    assert _aspect_span_deg(full) > 300.0

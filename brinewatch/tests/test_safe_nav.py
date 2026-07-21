"""Engine-free tests for collision-safe navigation around the outfall."""
import math

import numpy as np
import pytest

from brinewatch.planning.safe_nav import (
    Capsule, HazardField, SafeNavConfig, _seg_distance,
)
from brinewatch.simulation.outfall_scene import OutfallSceneConfig


def flat_bed(x, y):
    return -50.0


def _field(clearance=2.0, min_alt=1.0):
    cfg = SafeNavConfig(clearance_m=clearance, min_altitude_m=min_alt)
    # localized diffuser-start at (30, 0), axis +x (matches the mission scene)
    return HazardField.from_outfall((30.0, 0.0), 0.0, OutfallSceneConfig(),
                                    flat_bed, cfg)


def test_seg_distance_basics():
    a, b = np.array([0.0, 0, 0]), np.array([10.0, 0, 0])
    assert _seg_distance(np.array([5.0, 0, 0]), a, b) == pytest.approx(0.0)
    assert _seg_distance(np.array([5.0, 3, 0]), a, b) == pytest.approx(3.0)
    assert _seg_distance(np.array([-4.0, 0, 0]), a, b) == pytest.approx(4.0)  # past the end


def test_capsule_inside_is_negative():
    c = Capsule(np.array([0.0, 0, 0]), np.array([10.0, 0, 0]), 1.0)
    assert c.surface_distance(np.array([5.0, 0, 0])) == pytest.approx(-1.0)  # on axis
    assert c.surface_distance(np.array([5.0, 1.0, 0])) == pytest.approx(0.0)  # on surface
    assert c.surface_distance(np.array([5.0, 3.0, 0])) == pytest.approx(2.0)  # outside


def test_field_flags_point_over_a_riser_unsafe():
    f = _field(clearance=2.0, min_alt=1.0)
    # a riser sits at world x = 30 + 1.8 = 31.8, y = 0; flying 1.2 m above the
    # bed right over it is inside the 2 m standoff -> unsafe
    p_over_riser = np.array([31.8, 0.0, -50.0 + 1.2])
    assert not f.is_safe(p_over_riser)
    # well above and to the side is safe
    p_clear = np.array([31.8, 12.0, -50.0 + 6.0])
    assert f.is_safe(p_clear)


def test_altitude_floor_enforced():
    f = _field(min_alt=1.5)
    below = np.array([10.0, 20.0, -50.0 + 0.5])   # over the buried pipe area, too low
    assert not f.is_safe(below)
    assert f.altitude(below) == pytest.approx(0.5)
    lifted = f.project_to_safe(below)
    assert lifted[2] >= -50.0 + 1.5 - 1e-6


def test_project_to_safe_makes_points_safe():
    f = _field(clearance=2.0, min_alt=1.0)
    rng = np.random.default_rng(0)
    for _ in range(40):
        p = np.array([30.0 + rng.uniform(-2, 22),
                      rng.uniform(-3, 3),
                      -50.0 + rng.uniform(0.0, 2.0)])
        q = f.project_to_safe(p)
        assert f.is_safe(q), (p, q, f.clearance(q))


def test_safe_path_leaves_clear_leg_untouched():
    f = _field()
    a = np.array([10.0, 25.0, -50.0 + 6.0])
    b = np.array([50.0, 25.0, -50.0 + 6.0])       # far to the side, high up
    wps, ok = f.safe_path(a, b)
    assert ok
    assert len(wps) == 1
    assert np.allclose(wps[0], f.project_to_safe(b))


def test_safe_path_detours_across_the_diffuser():
    f = _field(clearance=2.0, min_alt=1.0)
    # SAFE start (the mission invariant), then a leg that would otherwise skim
    # low straight along the diffuser line, crossing every riser
    a = np.array([26.0, 0.0, -50.0 + 3.5])
    assert f.is_safe(a)
    b = np.array([50.0, 0.0, -50.0 + 1.5])         # low, near the diffuser end
    wps, ok = f.safe_path(a, b)
    assert ok
    assert len(wps) >= 2                            # at least one detour inserted
    # every sub-leg from the (safe) start is clear
    prev = a
    for w in wps:
        assert f.segment_safe(prev, w)
        prev = w
    # and it climbed over (max detour z above both endpoints)
    assert max(w[2] for w in wps) > -50.0 + 1.5 + 1.0


def test_safe_path_escapes_an_unsafe_start():
    f = _field(clearance=2.0, min_alt=1.0)
    a = np.array([28.0, 0.0, -50.0 + 1.5])         # within the pipe standoff
    assert not f.is_safe(a)
    b = np.array([50.0, 20.0, -50.0 + 5.0])        # safe, off to the side
    wps, ok = f.safe_path(a, b)
    assert ok
    assert f.is_safe(wps[0])                        # first move escapes to safety
    # every sub-leg between returned waypoints is clear
    prev = wps[0]
    for w in wps[1:]:
        assert f.segment_safe(prev, w)
        prev = w


def test_safe_path_endpoint_reaches_projected_goal():
    f = _field()
    a = np.array([26.0, 0.0, -50.0 + 3.5])
    b = np.array([50.0, 0.0, -50.0 + 1.5])
    wps, ok = f.safe_path(a, b)
    goal = f.project_to_safe(b)
    assert np.allclose(wps[-1], goal)

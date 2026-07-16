"""Tests for the survey planners (lawnmower baseline and adaptive GP planner)."""
from __future__ import annotations

from typing import List

import numpy as np
import pytest

from brinewatch.mapping.gp_mapper import GPMapper
from brinewatch.planning.adaptive import AdaptivePlanner
from brinewatch.planning.lawnmower import LawnmowerPlanner
from brinewatch.plume.model import BrinePlume
from brinewatch.utils.config import MissionConfig
from brinewatch.utils.geometry import boustrophedon
from brinewatch.utils.types import CTDSample, MissionBudget, VehicleState, Waypoint


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def cfg() -> MissionConfig:
    return MissionConfig()


@pytest.fixture(scope="module")
def plume(cfg: MissionConfig) -> BrinePlume:
    return BrinePlume(cfg.environment, cfg.outfall, cfg.plume)


@pytest.fixture()
def seabed_fn(plume: BrinePlume):
    return lambda x, y: float(plume.seabed_z(x, y))


@pytest.fixture()
def empty_mapper(cfg: MissionConfig, plume: BrinePlume) -> GPMapper:
    return GPMapper(cfg.gp, plume.ambient_salinity, seed=0)


def _boundary_psu(cfg: MissionConfig, plume: BrinePlume) -> float:
    """Compliance threshold, mirroring mission.runner.boundary_salinity_psu."""
    bed_z = float(plume.seabed_z(cfg.outfall.x, cfg.outfall.y))
    ambient_bottom = float(plume.ambient_salinity(bed_z))
    return ambient_bottom * (1.0 + cfg.compliance.threshold_increment_pct / 100.0)


def _state_at(plume: BrinePlume, cfg: MissionConfig, x: float, y: float, t: float = 0.0) -> VehicleState:
    z = float(plume.seabed_z(x, y)) + cfg.survey.altitude_m
    return VehicleState(t=t, x=x, y=y, z=z)


def _fitted_mapper(cfg: MissionConfig, plume: BrinePlume, n_side: int = 14) -> GPMapper:
    """A GPMapper trained on noiseless plume samples over a coarse survey grid."""
    mapper = GPMapper(cfg.gp, plume.ambient_salinity, seed=3)
    xs = np.linspace(cfg.survey.x_min, cfg.survey.x_max, n_side)
    ys = np.linspace(cfg.survey.y_min, cfg.survey.y_max, n_side)
    for x in xs:
        for y in ys:
            z = float(plume.seabed_z(x, y)) + cfg.survey.altitude_m
            s = float(plume.salinity(x, y, z, 0.0))
            t_c = float(plume.temperature(x, y, z, 0.0))
            mapper.add_sample(CTDSample(t=0.0, x=float(x), y=float(y), z=z,
                                        salinity_psu=s, temperature_c=t_c,
                                        depth_m=-z))
    return mapper


def _collect_adaptive(
    planner: AdaptivePlanner,
    mapper: GPMapper,
    plume: BrinePlume,
    cfg: MissionConfig,
    n_picks: int,
    budget_m: float = 1.0e6,
) -> List[Waypoint]:
    """Run the planner, walking the state to each returned waypoint."""
    state = _state_at(plume, cfg, 0.0, 0.0)
    budget = MissionBudget(budget_m)
    picks: List[Waypoint] = []
    for _ in range(n_picks):
        wp = planner.next_waypoint(state, mapper, budget)
        assert wp is not None
        picks.append(wp)
        state = VehicleState(t=state.t + 1.0, x=wp.x, y=wp.y, z=wp.z)
    return picks


# --------------------------------------------------------------------------- #
# Lawnmower
# --------------------------------------------------------------------------- #
def test_lawnmower_emits_full_pattern_in_order_then_none(cfg, plume, seabed_fn, empty_mapper):
    planner = LawnmowerPlanner(cfg.survey, cfg.lawnmower, seabed_fn)
    expected = boustrophedon(
        cfg.survey.x_min, cfg.survey.x_max, cfg.survey.y_min, cfg.survey.y_max,
        cfg.lawnmower.line_spacing_m, along_x=cfg.lawnmower.along_x,
    )
    state = _state_at(plume, cfg, 0.0, 0.0)
    budget = MissionBudget(1.0e6)

    got = []
    for _ in range(len(expected)):
        wp = planner.next_waypoint(state, empty_mapper, budget)
        assert wp is not None
        got.append(wp)

    assert len(got) == len(expected)
    for wp, (ex, ey) in zip(got, expected):
        assert wp.x == pytest.approx(ex)
        assert wp.y == pytest.approx(ey)
        assert wp.z == pytest.approx(seabed_fn(ex, ey) + cfg.survey.altitude_m)

    # Exhausted: None from now on.
    assert planner.next_waypoint(state, empty_mapper, budget) is None
    assert planner.next_waypoint(state, empty_mapper, budget) is None


def test_lawnmower_waypoints_within_survey_bounds(cfg, plume, seabed_fn, empty_mapper):
    planner = LawnmowerPlanner(cfg.survey, cfg.lawnmower, seabed_fn)
    state = _state_at(plume, cfg, 0.0, 0.0)
    budget = MissionBudget(1.0e6)
    while True:
        wp = planner.next_waypoint(state, empty_mapper, budget)
        if wp is None:
            break
        assert cfg.survey.x_min - 1e-9 <= wp.x <= cfg.survey.x_max + 1e-9
        assert cfg.survey.y_min - 1e-9 <= wp.y <= cfg.survey.y_max + 1e-9


def test_lawnmower_returns_waypoint_even_with_tiny_budget(cfg, plume, seabed_fn, empty_mapper):
    """Deterministic baseline: a nearly-exhausted budget does not stop the
    pattern (the runner hard-stops mid-leg instead)."""
    planner = LawnmowerPlanner(cfg.survey, cfg.lawnmower, seabed_fn)
    state = _state_at(plume, cfg, 0.0, 0.0)
    budget = MissionBudget(max_distance_m=100.0, used_m=99.5)
    assert planner.next_waypoint(state, empty_mapper, budget) is not None


# --------------------------------------------------------------------------- #
# Adaptive: geometry constraints
# --------------------------------------------------------------------------- #
def test_adaptive_in_bounds_and_survey_altitude(cfg, plume, seabed_fn, empty_mapper):
    planner = AdaptivePlanner(cfg.survey, cfg.adaptive, _boundary_psu(cfg, plume),
                              seabed_fn, seed=1)
    picks = _collect_adaptive(planner, empty_mapper, plume, cfg, n_picks=10)
    for wp in picks:
        assert cfg.survey.x_min <= wp.x <= cfg.survey.x_max
        assert cfg.survey.y_min <= wp.y <= cfg.survey.y_max
        assert wp.z == pytest.approx(seabed_fn(wp.x, wp.y) + cfg.survey.altitude_m)


def test_adaptive_leg_lengths_within_limits(cfg, plume, seabed_fn):
    mapper = _fitted_mapper(cfg, plume)
    planner = AdaptivePlanner(cfg.survey, cfg.adaptive, _boundary_psu(cfg, plume),
                              seabed_fn, seed=2)
    state = _state_at(plume, cfg, 0.0, 0.0)
    budget = MissionBudget(1.0e6)
    for _ in range(15):
        wp = planner.next_waypoint(state, mapper, budget)
        assert wp is not None
        d = state.distance_to(wp)
        # With 250 uniform candidates the [min_leg, max_leg] annulus is never
        # empty from inside the box, so the documented nearest-candidate
        # relaxation should not trigger with these seeds.
        assert cfg.adaptive.min_leg_m <= d <= cfg.adaptive.max_leg_m
        state = VehicleState(t=state.t + 1.0, x=wp.x, y=wp.y, z=wp.z)


def test_adaptive_min_separation_between_picks(cfg, plume, seabed_fn):
    mapper = _fitted_mapper(cfg, plume)
    planner = AdaptivePlanner(cfg.survey, cfg.adaptive, _boundary_psu(cfg, plume),
                              seabed_fn, seed=4)
    picks = _collect_adaptive(planner, mapper, plume, cfg, n_picks=12)
    xy = np.array([[wp.x, wp.y] for wp in picks])
    for i in range(len(xy)):
        for j in range(i + 1, len(xy)):
            d = float(np.hypot(*(xy[i] - xy[j])))
            assert d >= cfg.adaptive.min_separation_m, (
                f"picks {i} and {j} only {d:.2f} m apart"
            )


# --------------------------------------------------------------------------- #
# Adaptive: warmup and GP paths
# --------------------------------------------------------------------------- #
def test_adaptive_warmup_with_empty_mapper(cfg, plume, seabed_fn, empty_mapper):
    """With zero samples the planner must not touch the GP posterior and still
    produce valid, spread-out exploratory picks."""
    assert empty_mapper.n_samples == 0
    planner = AdaptivePlanner(cfg.survey, cfg.adaptive, _boundary_psu(cfg, plume),
                              seabed_fn, seed=5)
    picks = _collect_adaptive(planner, empty_mapper, plume, cfg, n_picks=8)
    xy = np.array([[wp.x, wp.y] for wp in picks])
    # Exploratory: picks span a non-trivial area rather than clumping.
    assert np.ptp(xy[:, 0]) > cfg.adaptive.min_separation_m
    assert np.ptp(xy[:, 1]) > cfg.adaptive.min_separation_m


def test_adaptive_concentrates_near_plume_boundary(cfg, plume, seabed_fn):
    """With a GP trained on plume data and boundary-dominant weights, picks
    must sit closer to the compliance isohaline (the plume boundary) than
    uniform random points do. This isolates the boundary term of the score
    (the exploration/std term legitimately pulls picks elsewhere when it
    dominates). Statistical but fully seeded, so deterministic."""
    import dataclasses

    boundary = _boundary_psu(cfg, plume)
    mapper = _fitted_mapper(cfg, plume)
    boundary_cfg = dataclasses.replace(
        cfg.adaptive, weight_std=0.2, weight_boundary=1.5, weight_travel=0.1
    )
    planner = AdaptivePlanner(cfg.survey, boundary_cfg, boundary, seabed_fn, seed=6)
    picks = _collect_adaptive(planner, mapper, plume, cfg, n_picks=30)

    def truth_gap(xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
        zs = np.asarray(plume.seabed_z(xs, ys)) + cfg.survey.altitude_m
        return np.abs(np.asarray(plume.salinity(xs, ys, zs, 0.0)) - boundary)

    px = np.array([wp.x for wp in picks])
    py = np.array([wp.y for wp in picks])
    adaptive_gap = float(np.mean(truth_gap(px, py)))

    rng = np.random.default_rng(123)
    ux = rng.uniform(cfg.survey.x_min, cfg.survey.x_max, 500)
    uy = rng.uniform(cfg.survey.y_min, cfg.survey.y_max, 500)
    uniform_gap = float(np.mean(truth_gap(ux, uy)))

    # Loose: on average, adaptive picks are clearly nearer the boundary
    # isohaline than uniform sampling of the box.
    assert adaptive_gap < 0.8 * uniform_gap, (
        f"adaptive mean |S - boundary| = {adaptive_gap:.3f} PSU, "
        f"uniform = {uniform_gap:.3f} PSU"
    )


# --------------------------------------------------------------------------- #
# Adaptive: budget
# --------------------------------------------------------------------------- #
def test_adaptive_returns_none_when_budget_nearly_exhausted(cfg, plume, seabed_fn, empty_mapper):
    planner = AdaptivePlanner(cfg.survey, cfg.adaptive, _boundary_psu(cfg, plume),
                              seabed_fn, seed=7)
    state = _state_at(plume, cfg, 0.0, 0.0)
    budget = MissionBudget(max_distance_m=1600.0,
                           used_m=1600.0 - 0.5 * cfg.adaptive.min_leg_m)
    assert budget.remaining_m < cfg.adaptive.min_leg_m
    assert planner.next_waypoint(state, empty_mapper, budget) is None

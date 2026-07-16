"""End-to-end mission tests on the kinematic backend (no HoloOcean needed)."""
from __future__ import annotations

import pytest

from brinewatch.mission.runner import create_mission
from brinewatch.utils.config import load_config

FAST_OVERRIDES = {
    "budget": {"max_distance_m": 500.0, "checkpoints": [0.5, 1.0]},
    "survey": {"grid_resolution_m": 6.0},
    "gp": {"max_train_points": 300},
}

PHASES = ("locate", "baseline", "survey", "done")


@pytest.mark.parametrize("planner", ["lawnmower", "adaptive"])
def test_full_mission(planner):
    cfg = load_config(None, overrides=FAST_OVERRIDES)
    runner = create_mission(cfg, planner_name=planner, backend_name="kinematic")
    try:
        result = runner.run()
    finally:
        runner.backend.close()

    assert len(result.samples) > 30
    assert result.budget.used_m <= cfg.budget.max_distance_m * 1.02 + 20
    assert result.outfall_estimate is not None
    phases_seen = {p for _, p in result.phase_history}
    for phase in PHASES:
        assert phase in phases_seen, f"missing phase {phase}"
    # budget_at_sample aligned and non-decreasing
    assert len(result.budget_at_sample) == len(result.samples)
    assert all(b1 <= b2 for b1, b2 in
               zip(result.budget_at_sample[:-1], result.budget_at_sample[1:]))
    assert len(result.trajectory) > 100


def test_budget_fairness_between_planners():
    """Both strategies must consume (nearly) the same budget — that is the
    core fairness property of the comparison."""
    used = {}
    for planner in ("lawnmower", "adaptive"):
        cfg = load_config(None, overrides=FAST_OVERRIDES)
        runner = create_mission(cfg, planner_name=planner, backend_name="kinematic")
        try:
            result = runner.run()
        finally:
            runner.backend.close()
        used[planner] = result.budget.used_m

    max_budget = 500.0
    both_maxed = all(u >= 0.95 * max_budget for u in used.values())
    within_5pct = abs(used["lawnmower"] - used["adaptive"]) <= 0.05 * max_budget
    assert both_maxed or within_5pct, f"budgets diverge: {used}"


def test_outfall_estimate_is_reasonable():
    cfg = load_config(None, overrides=FAST_OVERRIDES)
    runner = create_mission(cfg, planner_name="adaptive", backend_name="kinematic")
    try:
        result = runner.run()
    finally:
        runner.backend.close()
    ex, ey = result.outfall_estimate
    err = ((ex - cfg.outfall.x) ** 2 + (ey - cfg.outfall.y) ** 2) ** 0.5
    # Either confirmed by the locator (few metres) or prior fallback (~2 sigma)
    assert err < 3.0 * cfg.locator.prior_sigma_m

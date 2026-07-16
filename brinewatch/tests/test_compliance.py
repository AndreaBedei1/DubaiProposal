"""Tests for brinewatch.evaluation.compliance."""
from __future__ import annotations

import math

import numpy as np
import pytest

from brinewatch.evaluation.compliance import evaluate_compliance
from brinewatch.mapping.grid_map import EvalGrid
from brinewatch.utils.config import ComplianceConfig, SurveyConfig

AMBIENT = 40.0
OUTFALL = (0.0, 0.0)


def _flat_seabed(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    return np.full_like(np.asarray(x, dtype=float), -20.0)


@pytest.fixture()
def grid() -> EvalGrid:
    # 5x5 nodes at x, y in {-10, -5, 0, 5, 10}.
    survey = SurveyConfig(x_min=-10.0, x_max=10.0, y_min=-10.0, y_max=10.0, grid_resolution_m=5.0)
    return EvalGrid(survey, _flat_seabed, altitude_m=1.0)


@pytest.fixture()
def cfg() -> ComplianceConfig:
    # threshold = 40 * 1.05 = 42 PSU; zone keeps the 5-node plus at the centre.
    return ComplianceConfig(mixing_zone_radius_m=6.0, threshold_increment_pct=5.0)


def _node_index(grid: EvalGrid, x: float, y: float) -> int:
    return int(np.argmin(np.hypot(grid.X.ravel() - x, grid.Y.ravel() - y)))


def test_pass_when_exceedance_only_inside_zone(grid, cfg):
    mean = np.full(grid.X.size, AMBIENT)
    inside = ~grid.mask_outside_radius(*OUTFALL, cfg.mixing_zone_radius_m)
    assert inside.sum() == 5  # (0,0) and the four 5 m neighbours
    mean[inside] = 50.0  # hot, but inside the mixing zone

    v = evaluate_compliance(mean, None, grid, OUTFALL, cfg, AMBIENT)
    assert v.compliant is True
    assert v.label == "PASS"
    assert v.threshold_psu == pytest.approx(42.0)
    assert v.n_cells_exceeding == 0
    assert v.prob_exceed_max == 0.0
    # Margin: negative exceedance equal to (max outside mean) - threshold.
    assert v.max_exceedance_psu == pytest.approx(AMBIENT - 42.0)
    assert v.max_exceedance_psu < 0.0
    # The worst point is an outside node.
    assert math.hypot(v.worst_point[0], v.worst_point[1]) > cfg.mixing_zone_radius_m
    assert v.mixing_zone_radius_m == cfg.mixing_zone_radius_m


def test_fail_when_hotspot_outside_zone(grid, cfg):
    mean = np.full(grid.X.size, AMBIENT)
    mean[_node_index(grid, 10.0, 10.0)] = 43.0

    v = evaluate_compliance(mean, None, grid, OUTFALL, cfg, AMBIENT)
    assert v.compliant is False
    assert v.label == "FAIL"
    assert v.max_exceedance_psu == pytest.approx(1.0)
    assert v.worst_point == (10.0, 10.0)
    assert v.n_cells_exceeding == 1
    assert v.prob_exceed_max == 1.0  # indicator with std=None


def test_inside_hotspot_is_ignored(grid, cfg):
    mean = np.full(grid.X.size, AMBIENT)
    mean[_node_index(grid, 0.0, 0.0)] = 60.0
    v = evaluate_compliance(mean, None, grid, OUTFALL, cfg, AMBIENT)
    assert v.compliant is True
    assert v.n_cells_exceeding == 0


def test_n_cells_exceeding_counts_only_outside(grid, cfg):
    mean = np.full(grid.X.size, AMBIENT)
    for xy in [(10.0, 10.0), (-10.0, -10.0), (10.0, -5.0)]:
        mean[_node_index(grid, *xy)] = 44.0
    mean[_node_index(grid, 0.0, 5.0)] = 55.0  # inside the zone, must not count
    v = evaluate_compliance(mean, None, grid, OUTFALL, cfg, AMBIENT)
    assert v.n_cells_exceeding == 3
    assert v.compliant is False


def test_prob_exceed_with_gp_std(grid, cfg):
    n = grid.X.size
    # Far-exceeding mean with tiny std: probability ~ 1.
    mean = np.full(n, AMBIENT)
    mean[_node_index(grid, 10.0, 0.0)] = 45.0
    v_hot = evaluate_compliance(mean, np.full(n, 0.01), grid, OUTFALL, cfg, AMBIENT)
    assert 0.0 <= v_hot.prob_exceed_max <= 1.0
    assert v_hot.prob_exceed_max > 0.999

    # Compliant mean with tiny std: probability ~ 0.
    calm = np.full(n, AMBIENT)
    v_calm = evaluate_compliance(calm, np.full(n, 0.01), grid, OUTFALL, cfg, AMBIENT)
    assert 0.0 <= v_calm.prob_exceed_max <= 1.0
    assert v_calm.prob_exceed_max < 1e-6

    # Borderline: mean exactly at threshold with std > 0 gives ~0.5.
    edge = np.full(n, AMBIENT)
    edge[_node_index(grid, 10.0, 0.0)] = 42.0
    v_edge = evaluate_compliance(edge, np.full(n, 0.5), grid, OUTFALL, cfg, AMBIENT)
    assert v_edge.prob_exceed_max == pytest.approx(0.5, abs=1e-9)


def test_std_zeros_falls_back_to_indicator(grid, cfg):
    n = grid.X.size
    mean = np.full(n, AMBIENT)
    mean[_node_index(grid, 10.0, 10.0)] = 43.0
    v = evaluate_compliance(mean, np.zeros(n), grid, OUTFALL, cfg, AMBIENT)
    assert v.prob_exceed_max == 1.0
    calm = evaluate_compliance(np.full(n, AMBIENT), np.zeros(n), grid, OUTFALL, cfg, AMBIENT)
    assert calm.prob_exceed_max == 0.0


def test_mixed_zero_std_cells_use_indicator(grid, cfg):
    n = grid.X.size
    mean = np.full(n, AMBIENT)
    idx = _node_index(grid, 10.0, 10.0)
    mean[idx] = 43.0
    std = np.full(n, 0.5)
    std[idx] = 0.0  # exceeding cell has zero std: indicator applies there
    v = evaluate_compliance(mean, std, grid, OUTFALL, cfg, AMBIENT)
    assert v.prob_exceed_max == 1.0


def test_zone_covering_whole_grid_is_trivially_compliant(grid):
    cfg = ComplianceConfig(mixing_zone_radius_m=100.0, threshold_increment_pct=5.0)
    mean = np.full(grid.X.size, 60.0)
    v = evaluate_compliance(mean, None, grid, OUTFALL, cfg, AMBIENT)
    assert v.compliant is True
    assert v.n_cells_exceeding == 0
    assert v.prob_exceed_max == 0.0
    assert math.isnan(v.max_exceedance_psu)


def test_shape_mismatch_raises(grid, cfg):
    with pytest.raises(ValueError):
        evaluate_compliance(np.full(3, AMBIENT), None, grid, OUTFALL, cfg, AMBIENT)
    with pytest.raises(ValueError):
        evaluate_compliance(np.full(grid.X.size, AMBIENT), np.zeros(3), grid, OUTFALL, cfg, AMBIENT)

"""Tests for brinewatch.evaluation.metrics."""
from __future__ import annotations

import math
from typing import List

import numpy as np
import pytest

from brinewatch.evaluation.metrics import compute_metrics
from brinewatch.mapping.grid_map import EvalGrid
from brinewatch.plume.model import BrinePlume
from brinewatch.utils.config import EnvironmentConfig, OutfallConfig, PlumeConfig, SurveyConfig
from brinewatch.utils.types import CTDSample

THRESHOLD_PSU = 41.5  # comfortably between ambient (~39.7) and the plume core


def _sample(x: float, y: float, z: float, t: float = 0.0) -> CTDSample:
    return CTDSample(t=t, x=x, y=y, z=z, salinity_psu=40.0, temperature_c=24.0, depth_m=-z)


@pytest.fixture(scope="module")
def plume() -> BrinePlume:
    return BrinePlume(EnvironmentConfig(), OutfallConfig(), PlumeConfig())


@pytest.fixture(scope="module")
def grid(plume: BrinePlume) -> EvalGrid:
    survey = SurveyConfig(x_min=-60.0, x_max=60.0, y_min=-60.0, y_max=60.0, grid_resolution_m=6.0)
    return EvalGrid(survey, plume.seabed_z, altitude_m=1.0)


@pytest.fixture(scope="module")
def truth(plume: BrinePlume, grid: EvalGrid) -> np.ndarray:
    return plume.ground_truth(grid.points, t=0.0)


@pytest.fixture(scope="module")
def dense_samples(grid: EvalGrid) -> List[CTDSample]:
    pts = grid.points
    return [_sample(float(p[0]), float(p[1]), float(p[2])) for p in pts]


def test_perfect_reconstruction(plume, grid, truth, dense_samples):
    m = compute_metrics(truth.copy(), truth, grid, dense_samples, THRESHOLD_PSU, plume=plume)
    assert m.rmse_all == pytest.approx(0.0, abs=1e-12)
    assert m.rmse_plume == pytest.approx(0.0, abs=1e-12)
    assert m.mae_all == pytest.approx(0.0, abs=1e-12)
    assert m.boundary_f1 == pytest.approx(1.0)
    assert m.boundary_iou == pytest.approx(1.0)
    assert m.n_samples == len(dense_samples)


def test_bias_increases_rmse(plume, grid, truth, dense_samples):
    perfect = compute_metrics(truth.copy(), truth, grid, dense_samples, THRESHOLD_PSU, plume=plume)
    biased = compute_metrics(truth + 1.0, truth, grid, dense_samples, THRESHOLD_PSU, plume=plume)
    assert biased.rmse_all > perfect.rmse_all
    assert biased.rmse_all == pytest.approx(1.0, abs=1e-9)
    assert biased.mae_all == pytest.approx(1.0, abs=1e-9)
    assert biased.rmse_plume == pytest.approx(1.0, abs=1e-9)


def test_shifted_field_degrades_boundary(plume, grid, truth, dense_samples):
    # Shift the predicted image 3 cells (18 m) along x: the isohaline moves.
    shifted = np.roll(grid.reshape(truth), 3, axis=1).ravel()
    m = compute_metrics(shifted, truth, grid, dense_samples, THRESHOLD_PSU, plume=plume)
    assert (truth > THRESHOLD_PSU).any()  # the boundary exists in truth
    assert m.boundary_f1 < 1.0
    assert m.boundary_iou < 1.0
    assert m.boundary_iou <= m.boundary_f1  # IoU never exceeds F1
    assert m.rmse_all > 0.0


def test_empty_true_mask_conventions(plume, grid, truth, dense_samples):
    # Threshold far above anything in the field: true mask empty.
    high = float(np.max(truth)) + 10.0
    both_empty = compute_metrics(truth.copy(), truth, grid, dense_samples, high, plume=plume)
    assert both_empty.boundary_f1 == 1.0
    assert both_empty.boundary_iou == 1.0

    hot = truth.copy()
    hot[0] = high + 5.0  # predicted mask non-empty, true mask still empty
    false_alarm = compute_metrics(hot, truth, grid, dense_samples, high, plume=plume)
    assert false_alarm.boundary_f1 == 0.0
    assert false_alarm.boundary_iou == 0.0


def test_coverage_dense_and_corner(plume, grid, truth, dense_samples):
    dense = compute_metrics(truth.copy(), truth, grid, dense_samples, THRESHOLD_PSU,
                            plume=plume, coverage_radius_m=8.0)
    assert dense.coverage_frac == pytest.approx(1.0)

    corner = [_sample(-58.0 + dx, -58.0 + dy, -33.0) for dx in (0.0, 2.0) for dy in (0.0, 2.0)]
    clustered = compute_metrics(truth.copy(), truth, grid, corner, THRESHOLD_PSU,
                                plume=plume, coverage_radius_m=8.0)
    assert 0.0 < clustered.coverage_frac < 0.05
    assert clustered.n_samples == 4


def test_coverage_zero_without_samples(plume, grid, truth):
    m = compute_metrics(truth.copy(), truth, grid, [], THRESHOLD_PSU, plume=plume)
    assert m.coverage_frac == 0.0
    assert m.n_samples == 0
    assert math.isnan(m.in_plume_frac)


def test_in_plume_frac(plume, grid, truth):
    # Near the far-field impact point, hugging the seabed: strong anomaly.
    zx = float(plume.seabed_z(-24.0, 0.0)) + 0.5
    in_plume = [_sample(-24.0, y, zx) for y in (-2.0, 0.0, 2.0)]
    m_in = compute_metrics(truth.copy(), truth, grid, in_plume, THRESHOLD_PSU, plume=plume)
    assert m_in.in_plume_frac == pytest.approx(1.0)

    # Far corner, well off the plume axis: blue water.
    zb = float(plume.seabed_z(55.0, 55.0)) + 1.0
    blue = [_sample(55.0, 55.0 - k, zb) for k in (0.0, 1.0, 2.0)]
    m_blue = compute_metrics(truth.copy(), truth, grid, blue, THRESHOLD_PSU, plume=plume)
    assert m_blue.in_plume_frac == pytest.approx(0.0)

    mixed = in_plume + blue
    m_mixed = compute_metrics(truth.copy(), truth, grid, mixed, THRESHOLD_PSU, plume=plume)
    assert m_mixed.in_plume_frac == pytest.approx(0.5)


def test_in_plume_frac_nan_without_plume(grid, truth, dense_samples):
    m = compute_metrics(truth.copy(), truth, grid, dense_samples, THRESHOLD_PSU, plume=None)
    assert math.isnan(m.in_plume_frac)
    # The other metrics still work without a plume model.
    assert m.rmse_all == pytest.approx(0.0, abs=1e-12)
    assert m.boundary_f1 == pytest.approx(1.0)


def test_shape_mismatch_raises(plume, grid, truth):
    with pytest.raises(ValueError):
        compute_metrics(truth[:-1], truth, grid, [], THRESHOLD_PSU, plume=plume)

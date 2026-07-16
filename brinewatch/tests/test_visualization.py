"""Smoke tests for figures and the HTML mission report."""
from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from brinewatch.evaluation.compliance import ComplianceVerdict
from brinewatch.evaluation.metrics import MetricsResult
from brinewatch.mapping.grid_map import EvalGrid
from brinewatch.plume.model import BrinePlume
from brinewatch.utils.config import MissionConfig
from brinewatch.utils.types import CTDSample, MissionBudget, MissionResult
from brinewatch.visualization.plots import (
    plot_compliance_map,
    plot_learning_curves,
    plot_truth_vs_reconstruction,
)
from brinewatch.visualization.report import render_html_report


@pytest.fixture()
def cfg() -> MissionConfig:
    cfg = MissionConfig()
    cfg.survey = dataclasses.replace(
        cfg.survey, x_min=-30, x_max=30, y_min=-30, y_max=30, grid_resolution_m=5.0
    )
    return cfg


@pytest.fixture()
def plume(cfg) -> BrinePlume:
    return BrinePlume(cfg.environment, cfg.outfall, cfg.plume)


@pytest.fixture()
def grid(cfg, plume) -> EvalGrid:
    return EvalGrid(cfg.survey, plume.seabed_z, cfg.compliance.eval_altitude_m)


@pytest.fixture()
def fields(grid, plume):
    truth = plume.ground_truth(grid.points, t=0.0)
    rng = np.random.default_rng(0)
    mean = truth + rng.normal(0, 0.2, truth.shape)
    std = np.full_like(truth, 0.4)
    return truth, mean, std


@pytest.fixture()
def samples():
    return [CTDSample(t=float(i), x=float(-20 + 3 * i), y=float(-10 + 2 * i),
                      z=-32.0, salinity_psu=40.0 + 0.1 * i, temperature_c=24.0,
                      depth_m=32.0) for i in range(10)]


def _verdict(compliant: bool) -> ComplianceVerdict:
    return ComplianceVerdict(
        compliant=compliant, threshold_psu=41.65, max_exceedance_psu=-0.4 if compliant else 0.7,
        worst_point=(12.0, 3.0), prob_exceed_max=0.05 if compliant else 0.93,
        n_cells_exceeding=0 if compliant else 7, mixing_zone_radius_m=40.0,
    )


def test_truth_vs_reconstruction_png(grid, fields, samples, tmp_path):
    truth, mean, std = fields
    traj = [(float(i), float(-25 + i), float(-25 + i), -32.0) for i in range(30)]
    out = plot_truth_vs_reconstruction(
        grid, truth, mean, std, samples, traj, (-30.0, 0.0), 40.0, 41.65,
        tmp_path / "fig1.png", title="test")
    assert out.exists() and out.stat().st_size > 5000


def test_compliance_map_png(grid, fields, tmp_path):
    _, mean, _ = fields
    out = plot_compliance_map(grid, mean, 41.65, (-30.0, 0.0), 40.0,
                              tmp_path / "fig2.png", worst_point=(12.0, 3.0),
                              title="exceedance")
    assert out.exists() and out.stat().st_size > 5000


def test_learning_curves_png(tmp_path):
    records = []
    for planner in ("lawnmower", "adaptive"):
        for seed in (0, 1):
            for frac, budget in ((0.5, 800.0), (1.0, 1600.0)):
                records.append({
                    "planner": planner, "seed": seed, "checkpoint_frac": frac,
                    "budget_m": budget,
                    "rmse_plume": 1.0 - 0.3 * frac - (0.1 if planner == "adaptive" else 0),
                    "boundary_f1": 0.5 + 0.3 * frac,
                    "coverage_frac": 0.4 + 0.4 * frac,
                })
    out = plot_learning_curves(records, tmp_path / "curves.png")
    assert out.exists() and out.stat().st_size > 5000


def test_html_report(cfg, grid, fields, samples, tmp_path):
    truth, mean, std = fields
    fig = plot_compliance_map(grid, mean, 41.65, (-30.0, 0.0), 40.0, tmp_path / "f.png")
    result = MissionResult(planner_name="adaptive", samples=samples,
                           budget_at_sample=[10.0 * i for i in range(len(samples))],
                           trajectory=[(0.0, 0.0, 0.0, -30.0)],
                           outfall_estimate=(-29.0, 1.0),
                           budget=MissionBudget(1600.0, 1400.0),
                           phase_history=[(0.0, "locate"), (100.0, "survey")],
                           wall_time_s=12.0)
    metrics = MetricsResult(rmse_all=0.2, rmse_plume=0.5, mae_all=0.15,
                            boundary_f1=0.8, boundary_iou=0.7, coverage_frac=0.9,
                            n_samples=len(samples), in_plume_frac=0.4)
    out = render_html_report(
        tmp_path / "report.html", cfg, result, _verdict(False), _verdict(False),
        metrics, figures={"Compliance": fig})
    text = out.read_text(encoding="utf-8")
    assert "FAIL" in text
    assert "data:image/png;base64" in text
    assert "Approximations" in text or "approximations" in text.lower()


def test_html_report_pass_banner(cfg, grid, fields, samples, tmp_path):
    truth, mean, std = fields
    result = MissionResult(planner_name="lawnmower", samples=samples,
                           budget_at_sample=[10.0 * i for i in range(len(samples))],
                           budget=MissionBudget(1600.0, 1500.0))
    out = render_html_report(
        tmp_path / "report_pass.html", cfg, result, _verdict(True), None, None,
        figures={})
    text = out.read_text(encoding="utf-8")
    assert "PASS" in text

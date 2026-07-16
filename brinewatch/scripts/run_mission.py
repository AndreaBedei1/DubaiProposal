"""Run one BrineWatch mission end-to-end and produce the digital-twin report.

Usage (from the repo root, inside the conda env that has brinewatch installed):

    python scripts/run_mission.py --config configs/mission_default.yaml
    python scripts/run_mission.py --planner lawnmower --backend kinematic
    python scripts/run_mission.py --config configs/holoocean_live.yaml
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from brinewatch.evaluation.compliance import evaluate_compliance
from brinewatch.evaluation.metrics import compute_metrics
from brinewatch.evaluation.screening import screen, screening_outcome
from brinewatch.mapping.grid_map import EvalGrid
from brinewatch.mission.runner import boundary_salinity_psu, create_mission
from brinewatch.utils.config import load_config, save_config
from brinewatch.utils.logging_utils import (
    MissionLogger,
    make_run_dir,
    save_result_summary,
    save_samples_csv,
)
from brinewatch.visualization.plots import plot_compliance_map, plot_truth_vs_reconstruction
from brinewatch.visualization.report import render_html_report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", type=str, default=None, help="YAML mission config")
    ap.add_argument("--planner", type=str, default=None, choices=[None, "lawnmower", "adaptive"])
    ap.add_argument("--backend", type=str, default=None, choices=[None, "kinematic", "holoocean"])
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--out", type=str, default=str(REPO_ROOT / "outputs"))
    args = ap.parse_args()

    overrides = {}
    if args.seed is not None:
        overrides["seed"] = args.seed
    cfg = load_config(args.config, overrides=overrides or None)
    planner_name = args.planner or cfg.planner
    backend_name = args.backend or cfg.backend.name

    run_dir = make_run_dir(args.out, f"{cfg.name}_{planner_name}_{backend_name}")
    print(f"[brinewatch] run dir: {run_dir}")

    with MissionLogger(run_dir) as logger:
        runner = create_mission(cfg, planner_name=planner_name,
                                backend_name=backend_name, logger=logger)
        try:
            result = runner.run()
        finally:
            runner.backend.close()

    # ----------------------------------------------------------------- #
    # Reconstruction, metrics, compliance
    # ----------------------------------------------------------------- #
    plume = runner.plume
    grid = EvalGrid(cfg.survey, plume.seabed_z, cfg.compliance.eval_altitude_m)
    truth = plume.ground_truth(grid.points, t=0.0)
    mean, std = runner.mapper.predict(grid.points)

    bed_out = float(plume.seabed_z(cfg.outfall.x, cfg.outfall.y))
    ambient_bottom = float(plume.ambient_salinity(bed_out))
    threshold = boundary_salinity_psu(cfg, plume)
    true_xy = plume.outfall_xy()

    verdict = evaluate_compliance(mean, std, grid, true_xy, cfg.compliance, ambient_bottom)
    gt_verdict = evaluate_compliance(truth, None, grid, true_xy, cfg.compliance, ambient_bottom)
    metrics = compute_metrics(mean, truth, grid, result.samples, threshold, plume=plume)
    screening = screen(verdict, cfg.compliance)
    outcome = screening_outcome(screening, gt_verdict.compliant)

    # ----------------------------------------------------------------- #
    # Artifacts
    # ----------------------------------------------------------------- #
    save_config(cfg, run_dir / "config_used.yaml")
    save_samples_csv(result.samples, result.budget_at_sample, run_dir / "samples.csv")
    np.savez_compressed(
        run_dir / "plume_maps.npz",
        mean=grid.reshape(mean), std=grid.reshape(std), truth=grid.reshape(truth),
        X=grid.X, Y=grid.Y, Z=grid.Z,
        trajectory=np.asarray(result.trajectory, dtype=float),  # (t, x, y, z)
    )
    fig1 = plot_truth_vs_reconstruction(
        grid, truth, mean, std, result.samples, result.trajectory,
        true_xy, cfg.compliance.mixing_zone_radius_m, threshold,
        run_dir / "map_truth_vs_reconstruction.png",
        title=f"{planner_name} on {backend_name}",
    )
    fig2 = plot_compliance_map(
        grid, mean, threshold, true_xy, cfg.compliance.mixing_zone_radius_m,
        run_dir / "map_compliance.png", worst_point=verdict.worst_point,
        title=f"Exceedance vs threshold ({verdict.label})",
    )
    save_result_summary(result, run_dir / "summary.json", extra={
        "screening": screening.state.value,
        "screening_reason": screening.reason,
        "screening_outcome_vs_gt": outcome,
        "verdict_binary_legacy": verdict.label,
        "gt_verdict": gt_verdict.label,
        "threshold_psu": round(threshold, 3),
        "max_exceedance_psu": round(verdict.max_exceedance_psu, 3),
        "prob_exceed_max": round(verdict.prob_exceed_max, 3),
        "max_std_outside_psu": round(verdict.max_std_outside_psu, 3),
        "rmse_plume": round(metrics.rmse_plume, 4),
        "boundary_f1": round(metrics.boundary_f1, 3),
    })
    report = render_html_report(
        run_dir / "report.html", cfg, result, verdict, gt_verdict, metrics,
        figures={"Ground truth vs reconstruction": fig1, "Compliance map": fig2},
        screening=screening,
    )

    print(f"[brinewatch] planner={planner_name} backend={backend_name} "
          f"samples={len(result.samples)} budget={result.budget.used_m:.0f}/"
          f"{result.budget.max_distance_m:.0f} m")
    print(f"[brinewatch] screening: {screening.label} (vs GT: {outcome}) | "
          f"binary legacy: {verdict.label} / GT {gt_verdict.label} | "
          f"max exceedance {verdict.max_exceedance_psu:+.2f} PSU | "
          f"P(exceed) {verdict.prob_exceed_max:.2f} | "
          f"max std outside {verdict.max_std_outside_psu:.2f} PSU")
    print(f"[brinewatch] rmse(plume)={metrics.rmse_plume:.3f} PSU  "
          f"boundary F1={metrics.boundary_f1:.2f}  coverage={metrics.coverage_frac:.2f}")
    print(f"[brinewatch] report: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""PFH 2026 official demonstration: end-to-end BlueROV2 mission in official
HoloOcean with sonar-based (no ground-truth) outfall localization.

Stages:
1. environment checks (HoloOcean importable, config valid);
2. boot PierHarbor; automated terrain-calibration probe (down-looking
   RangeFinder on a grid) -> local TerrainMap + fitted reference plane;
3. build the visual outfall scene on the measured terrain (JSON manifest);
4. full mission LOCATE -> BASELINE -> SURVEY -> REPORT with the ImagingSonar
   localization pipeline (chart prior from config; the mission never reads
   the true outfall position);
5. post-mission evaluation (ground truth used ONLY here): localization
   error, reconstruction metrics, three-state screening, figures, report.

Usage:
    python scripts/run_pfh2026_demo.py [--config configs/pfh2026_holoocean.yaml]
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import math
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
from brinewatch.sensors.sonar_recorder import SonarRecorder
from brinewatch.simulation import make_backend
from brinewatch.utils.config import load_config, save_config
from brinewatch.utils.geometry import dist2
from brinewatch.utils.logging_utils import (
    MissionLogger,
    make_run_dir,
    save_result_summary,
    save_samples_csv,
)
from brinewatch.visualization.plots import plot_compliance_map, plot_truth_vs_reconstruction
from brinewatch.visualization.report import render_html_report


def fail(msg: str) -> int:
    print(f"[pfh2026] FATAL: {msg}")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", type=str,
                    default=str(REPO_ROOT / "configs" / "pfh2026_holoocean.yaml"))
    ap.add_argument("--out", type=str, default=str(REPO_ROOT / "outputs"))
    args = ap.parse_args()

    # ------------------------- 1. checks ------------------------------- #
    try:
        import holoocean  # noqa: F401
    except ImportError:
        return fail("HoloOcean is not importable in this environment")

    cfg = load_config(args.config)
    if cfg.locator.mode != "sonar":
        return fail("official demo requires locator.mode: sonar (no oracle)")
    if not cfg.backend.holoocean.sonar_enabled:
        return fail("official demo requires backend.holoocean.sonar_enabled: true")
    if cfg.locator.prior_x is None or cfg.locator.prior_y is None:
        return fail("official demo requires an explicit chart prior "
                    "(locator.prior_x/prior_y) — no ground-truth-derived priors")

    run_dir = make_run_dir(args.out, cfg.name)
    print(f"[pfh2026] run dir: {run_dir}")
    save_config(cfg, run_dir / "config_used.yaml")

    # ------------------------- 2. boot + terrain probe ------------------ #
    start = (
        0.5 * (cfg.survey.x_min + cfg.survey.x_max),
        0.5 * (cfg.survey.y_min + cfg.survey.y_max),
        cfg.environment.seabed_z0 + 8.0,
    )
    backend = make_backend("holoocean", cfg.backend, cfg.environment, cfg.outfall,
                           start, seed=cfg.seed + 41)
    try:
        upstream = math.radians(cfg.environment.current_dir_deg + 180.0)
        builder = backend.scene_builder(upstream_dir_rad=upstream)
        # Probe the WHOLE survey box (not just the outfall surroundings): the
        # fitted plane feeds the plume model and every waypoint depth, so it
        # must represent the survey area; the robust fit rejects soundings
        # that hit structures instead of the seabed.
        xs = np.linspace(cfg.survey.x_min + 8.0, cfg.survey.x_max - 8.0, 6)
        ys = np.linspace(cfg.survey.y_min + 8.0, cfg.survey.y_max - 8.0, 5)
        terrain = builder.probe_terrain(reference_bed_z=cfg.environment.seabed_z0,
                                        xs=xs, ys=ys)
        terrain.save_npz(run_dir / "terrain.npz")
        fit = terrain.fit_plane(robust=True)
        print(f"[pfh2026] terrain plane: z0={fit.z0:.2f} sx={fit.slope_x:.4f} "
              f"sy={fit.slope_y:.4f} rmse={fit.rmse_m:.2f} m")
        cfg_cal = dataclasses.replace(cfg, environment=dataclasses.replace(
            cfg.environment, seabed_z0=fit.z0,
            seabed_slope_x=fit.slope_x, seabed_slope_y=fit.slope_y))

        # --------------------- 3. visual outfall scene ------------------ #
        components = builder.build()
        builder.save_manifest(run_dir / "scene_manifest.json")

        # --------------------- 4. full mission -------------------------- #
        with MissionLogger(run_dir) as logger, \
                SonarRecorder(run_dir / "sonar_recording",
                              meta={"world": cfg.backend.holoocean.world,
                                    "config": str(args.config)}) as recorder:
            runner = create_mission(cfg_cal, logger=logger, backend=backend,
                                    sonar_recorder=recorder)
            result = runner.run()
    finally:
        backend.close()

    # ------------------------- 5. evaluation (GT allowed) --------------- #
    plume = runner.plume
    grid = EvalGrid(cfg_cal.survey, plume.seabed_z, cfg_cal.compliance.eval_altitude_m)
    truth = plume.ground_truth(grid.points, t=0.0)
    mean, std = runner.mapper.predict(grid.points)

    bed_out = float(plume.seabed_z(cfg_cal.outfall.x, cfg_cal.outfall.y))
    ambient_bottom = float(plume.ambient_salinity(bed_out))
    threshold = boundary_salinity_psu(cfg_cal, plume)
    true_xy = plume.outfall_xy()

    verdict = evaluate_compliance(mean, std, grid, true_xy, cfg_cal.compliance, ambient_bottom)
    gt_verdict = evaluate_compliance(truth, None, grid, true_xy, cfg_cal.compliance, ambient_bottom)
    metrics = compute_metrics(mean, truth, grid, result.samples, threshold, plume=plume)
    screening = screen(verdict, cfg_cal.compliance)
    outcome = screening_outcome(screening, gt_verdict.compliant)

    loc_error = float("nan")
    localized_by_sonar = bool(result.detections) and result.outfall_estimate is not None
    if result.outfall_estimate is not None:
        loc_error = dist2(result.outfall_estimate, true_xy)
    locator = runner.locator
    sonar_stats = {
        "frames_processed": getattr(locator, "frames_seen", None),
        "contacts_accepted": getattr(locator, "contacts_seen", None),
        "detections_emitted": len(result.detections),
        "localized_by_sonar": localized_by_sonar,
    }
    if not localized_by_sonar:
        print("[pfh2026] WARNING: outfall NOT confirmed by sonar - mission fell "
              "back to the chart prior. This run is NOT valid sonar-localization "
              "evidence; see mission_log.jsonl.")

    # Artifacts
    save_samples_csv(result.samples, result.budget_at_sample, run_dir / "samples.csv")
    np.savez_compressed(
        run_dir / "plume_maps.npz",
        mean=grid.reshape(mean), std=grid.reshape(std), truth=grid.reshape(truth),
        X=grid.X, Y=grid.Y, Z=grid.Z,
        trajectory=np.asarray(result.trajectory, dtype=float),
    )
    fig1 = plot_truth_vs_reconstruction(
        grid, truth, mean, std, result.samples, result.trajectory,
        true_xy, cfg_cal.compliance.mixing_zone_radius_m, threshold,
        run_dir / "map_truth_vs_reconstruction.png",
        title="PFH2026 official demo - adaptive on HoloOcean PierHarbor")
    fig2 = plot_compliance_map(
        grid, mean, threshold, true_xy, cfg_cal.compliance.mixing_zone_radius_m,
        run_dir / "map_compliance.png", worst_point=verdict.worst_point,
        title=f"Screening: {screening.label}")

    extra = {
        "screening": screening.state.value,
        "screening_outcome_vs_gt": outcome,
        "verdict_binary_legacy": verdict.label,
        "gt_verdict": gt_verdict.label,
        "localization_error_m": round(loc_error, 2),
        "sonar": sonar_stats,
        "acoustic_target": "official stock pier structure (PierHarbor)",
        "scene_components_ok": sum(1 for c in components if c.ok),
        "terrain_plane_rmse_m": round(fit.rmse_m, 3),
        "rmse_plume": round(metrics.rmse_plume, 4),
        "boundary_f1": round(metrics.boundary_f1, 3),
        "prob_exceed_max": round(verdict.prob_exceed_max, 3),
    }
    save_result_summary(result, run_dir / "summary.json", extra=extra)
    report = render_html_report(
        run_dir / "report.html", cfg_cal, result, verdict, gt_verdict, metrics,
        figures={"Ground truth vs reconstruction": fig1, "Compliance map": fig2},
        extra=extra, screening=screening)

    print(f"[pfh2026] mission: {len(result.samples)} samples, "
          f"budget {result.budget.used_m:.0f}/{result.budget.max_distance_m:.0f} m, "
          f"detections {len(result.detections)}")
    print(f"[pfh2026] localization: error {loc_error:.2f} m "
          f"(sonar-confirmed: {localized_by_sonar})")
    print(f"[pfh2026] screening: {screening.label} (vs GT: {outcome}) | "
          f"P(exceed) {verdict.prob_exceed_max:.2f} | rmse_plume {metrics.rmse_plume:.3f}")
    print(f"[pfh2026] report: {report}")
    (run_dir / "PFH2026_RUN_OK").write_text(json.dumps(extra, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

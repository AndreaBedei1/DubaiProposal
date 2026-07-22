"""PFH 2026 CUSTOM-ENGINE end-to-end mission (Demo 2) — motion AND sensing in
the custom HoloOcean fork, with collision-safe navigation.

Unlike run_custom_pfh2026_demo.py (custom-engine sonar LOCATE + kinematic
survey), here the BlueROV2 is driven THROUGH the survey inside the fork engine:
the survey trajectory, the CTD georeferencing and the collision flags all come
from the simulator. The plume/CTD salinity field remains the documented
analytic surrogate (BrineWatch never claims a CFD plume); everything about the
vehicle's motion and its sonar is the engine.

The reason the earlier demo kept the survey kinematic — "driving the real ROV
through the spawned structure collides" — is removed by the collision-safe
navigation layer (brinewatch/planning/safe_nav.py): a HazardField built from
the SONAR ESTIMATE plus the design-chart geometry (no ground truth) keeps a
standoff from the pipe / diffuser / risers and routes legs over the top.

Single fork-engine session (launch it first, see launch_custom_engine.py):
 1. attach (custom backend, auto-discovered in-project engine);
 2. terrain-calibration probe;
 3. BASELINE sonar ring (no outfall) — pre-installation baseline;
 4. spawn the multiport outfall (SpawnAsset -> octree rebuild);
 5. INSPECTION sonar ring at the same poses (outfall present) — this is also
    the pipe/diffuser/riser inspection evidence;
 6. LOCATE by pose-matched background subtraction (no GT; fallback disqualifies);
 7. build the HazardField from the estimate; drive the ROV to a safe start
    above/away; run BASELINE + adaptive SURVEY IN-ENGINE, collision-safe,
    sampling the analytic plume along the engine trajectory;
 8. GP reconstruction, three-state screening, report; post-mission evaluation
    (ground truth ONLY here): localization error, plume metrics, collisions,
    detours, minimum structure clearance.

Usage:
    python scripts/launch_custom_engine.py --clear-cache        # terminal 1
    python scripts/run_custom_holoocean_mission.py              # terminal 2
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import math
import os
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
from brinewatch.perception.insitu_locator import (
    InSituDiffuserLocator, InSituLocatorConfig)
from brinewatch.perception.sonar_background_locator import (
    BackgroundLocatorConfig, SonarBackgroundLocator)
from brinewatch.perception.sonar_diffuser_detector import DetectorConfig
from brinewatch.planning.safe_nav import HazardField, SafeNavConfig
from brinewatch.sensors.sonar_types import SonarFrame
from brinewatch.simulation import make_backend
from brinewatch.simulation.outfall_scene import OutfallSceneConfig
from brinewatch.utils.config import load_config, save_config
from brinewatch.utils.geometry import dist2
from brinewatch.utils.logging_utils import (
    MissionLogger, make_run_dir, save_result_summary, save_samples_csv)
from brinewatch.utils.types import Waypoint
from brinewatch.visualization.plots import (
    plot_compliance_map, plot_truth_vs_reconstruction)
from brinewatch.visualization.report import render_html_report


def fail(msg: str) -> int:
    print(f"[custom-mission] FATAL: {msg}")
    return 1


def ring_poses(center, radius, n, bed_fn, height=3.0):
    cx, cy = center
    poses = []
    for k in range(n):
        a = 2 * math.pi * k / n
        px, py = cx + radius * math.cos(a), cy + radius * math.sin(a)
        yaw = math.degrees(math.atan2(cy - py, cx - px))
        poses.append((f"r{int(radius):02d}_k{k:02d}", px, py,
                      float(bed_fn(px, py)) + height, yaw))
    return poses


def residual_frame(baseline: SonarFrame, live: SonarFrame) -> SonarFrame:
    """Return the positive, pose-matched sonar change image."""
    image = np.clip(np.asarray(live.image, np.float32)
                    - np.asarray(baseline.image, np.float32), 0.0, None)
    return SonarFrame(
        t=live.t, image=image, range_min_m=live.range_min_m,
        range_max_m=live.range_max_m, azimuth_fov_deg=live.azimuth_fov_deg,
        elevation_fov_deg=live.elevation_fov_deg,
        vehicle_xyz=live.vehicle_xyz, vehicle_rpy=live.vehicle_rpy,
        extrinsics=live.extrinsics)


def fit_diffuser(residuals, prior, cfg, seed):
    """Fit the diffuser line from residual frames without ground-truth input."""
    locator = InSituDiffuserLocator(InSituLocatorConfig(
        detector=DetectorConfig(min_range_m=6.0, z_threshold=3.5,
                                min_area_bins=8),
        prior_xy=prior, prior_gate_m=30.0,
        prior_axis_deg=cfg.outfall.axis_deg,
        corridor_halfwidth_m=10.0, line_inlier_m=4.0, min_inliers=6,
        min_aspect_span_deg=25.0, bootstrap=200), seed=seed)
    for frame in residuals:
        locator.ingest(frame)
    return locator.localize()


def uncertainty_weighted_estimate(locations):
    """Fuse non-fallback fits using inverse posterior-variance weights."""
    valid = [loc for loc in locations if not loc.fallback and loc.estimate]
    if not valid:
        return None, None
    weights = np.asarray([
        1.0 / max(float(loc.sigma_radius_m or 5.0), 0.5) ** 2
        for loc in valid
    ])
    points = np.asarray([loc.estimate for loc in valid], dtype=float)
    estimate = np.average(points, axis=0, weights=weights)
    sigma = float(math.sqrt(1.0 / weights.sum()))
    return (float(estimate[0]), float(estimate[1])), sigma


def drive_to(backend, wp, max_steps=400, tol=2.5):
    """Drive the live ROV toward ``wp`` (used to position it at a safe start
    before the mission runner takes over)."""
    for _ in range(max_steps):
        st = backend.step_toward(wp)
        if math.hypot(st.x - wp.x, st.y - wp.y) <= tol:
            return st
    return backend._last_state


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default=str(REPO_ROOT / "configs" / "pfh2026_custom.yaml"))
    ap.add_argument(
        "--out",
        default=os.environ.get("BRINEWATCH_SESSION_OUTPUT_DIR",
                               str(REPO_ROOT / "outputs")),
    )
    ap.add_argument("--ring-radius", type=float, default=22.0)
    ap.add_argument("--ring-radii", type=float, nargs="+", default=None,
                    help="confirmation radii; default uses 22 m and 15 m")
    ap.add_argument("--ring-poses", type=int, default=18)
    ap.add_argument("--budget", type=float, default=260.0,
                    help="in-engine survey travel budget (m); smaller than the "
                         "kinematic demo to keep the live run tractable")
    ap.add_argument("--clearance", type=float, default=2.0,
                    help="collision-safe standoff from the structure (m)")
    ap.add_argument("--prior-x", type=float, default=None,
                    help="override the chart prior x (else config)")
    ap.add_argument("--prior-y", type=float, default=None)
    args = ap.parse_args()

    config_path = Path(args.config)
    if not config_path.is_absolute() and not config_path.exists():
        config_path = REPO_ROOT / config_path
    cfg = load_config(config_path)
    if cfg.backend.name != "holoocean_custom":
        return fail("this mission requires backend.name: holoocean_custom")
    if cfg.locator.mode != "sonar":
        return fail("this mission requires locator.mode: sonar")
    if cfg.locator.prior_x is None or cfg.locator.prior_y is None:
        return fail("this mission requires an explicit chart prior")

    run_dir = make_run_dir(args.out, "custom_holoocean_mission")
    print(f"[custom-mission] run dir: {run_dir}")
    save_config(cfg, run_dir / "config_used.yaml")
    prior = (float(args.prior_x if args.prior_x is not None else cfg.locator.prior_x),
             float(args.prior_y if args.prior_y is not None else cfg.locator.prior_y))

    start = (0.5 * (cfg.survey.x_min + cfg.survey.x_max),
             0.5 * (cfg.survey.y_min + cfg.survey.y_max),
             cfg.environment.seabed_z0 + 8.0)
    backend = make_backend("holoocean_custom", cfg.backend, cfg.environment,
                           cfg.outfall, start, seed=cfg.seed + 41)
    result = None
    try:
        # ---- 2. terrain probe -------------------------------------------- #
        upstream = math.radians(cfg.environment.current_dir_deg + 180.0)
        builder = backend.scene_builder(upstream_dir_rad=upstream)
        xs = np.linspace(cfg.survey.x_min + 8.0, cfg.survey.x_max - 8.0, 6)
        ys = np.linspace(cfg.survey.y_min + 8.0, cfg.survey.y_max - 8.0, 5)
        terrain = builder.probe_terrain(reference_bed_z=cfg.environment.seabed_z0,
                                        xs=xs, ys=ys)
        terrain.save_npz(run_dir / "terrain.npz")
        fit = terrain.fit_plane(robust=True)
        print(f"[custom-mission] terrain plane z0={fit.z0:.2f} rmse={fit.rmse_m:.2f} m")
        cfg_cal = dataclasses.replace(
            cfg,
            environment=dataclasses.replace(
                cfg.environment, seabed_z0=fit.z0,
                seabed_slope_x=fit.slope_x, seabed_slope_y=fit.slope_y),
            budget=dataclasses.replace(cfg.budget, max_distance_m=args.budget))

        def bed_fn(x, y):
            return terrain.z(x, y)

        radii = args.ring_radii or [args.ring_radius, 15.0]
        radii = list(dict.fromkeys(round(float(r), 3) for r in radii))
        ring = [pose for radius in radii
                for pose in ring_poses(prior, radius, args.ring_poses,
                                       bed_fn)]

        # ---- 3. BASELINE sonar ring (no outfall) ------------------------- #
        print(f"[custom-mission] baseline sonar ring ({len(ring)} poses)...")
        baseline = {}
        for key, px, py, pz, yaw in ring:
            fr = backend.capture_sonar_at(px, py, pz, yaw)
            if fr is not None:
                baseline[key] = fr

        # ---- 4. spawn outfall (SpawnAsset -> octree rebuild) ------------- #
        components = builder.build()
        builder.save_manifest(run_dir / "scene_manifest.json")
        n_ok = sum(1 for c in components if c.ok)
        backend._tick_n(45, backend._hold_command())
        print(f"[custom-mission] spawned outfall: {n_ok} components")

        # ---- 5. INSPECTION sonar ring (same poses) ----------------------- #
        print("[custom-mission] inspection sonar ring (pipe/diffuser/risers)...")
        live = {}
        for key, px, py, pz, yaw in ring:
            fr = backend.capture_sonar_at(px, py, pz, yaw)
            if fr is not None:
                live[key] = fr
        np.savez_compressed(run_dir / "locate_baseline_frames.npz",
                            **{k: v.image for k, v in baseline.items()})
        np.savez_compressed(run_dir / "locate_inspection_frames.npz",
                            **{k: v.image for k, v in live.items()})

        # ---- 6. LOCATE (no GT): background subtraction + diffuser-line fit --
        # Background subtraction cancels clutter common to the baseline and
        # inspection passes; feeding the RESIDUAL frames to the in-situ diffuser
        # LINE locator additionally rejects off-axis spawned scene elements
        # (rock berm / scatter) that a plain densest-cluster consensus would
        # lock onto. The chart axis (pipeline bearing) constrains the fit; the
        # centre is the along-track midpoint of the inlier risers.
        blc = SonarBackgroundLocator(BackgroundLocatorConfig(
            prior_xy=prior, prior_gate_m=30.0))
        loc_ncontacts = 0
        residuals = {}
        for key in sorted(set(baseline) & set(live)):
            loc_ncontacts += blc.ingest(baseline[key], live[key])
            residuals[key] = residual_frame(baseline[key], live[key])
        bg_loc = blc.localize()
        loc = fit_diffuser(list(residuals.values()), prior, cfg, cfg.seed + 7)

        # Independent per-radius fits form the confirmation pass. The final
        # estimate is valid only if two aspects/radii agree; a failed check is
        # reported explicitly and never promoted as sonar localization.
        radius_fits = {}
        radius_locations = []
        for idx, radius in enumerate(radii):
            prefix = f"r{int(radius):02d}_"
            frames = [frame for key, frame in residuals.items()
                      if key.startswith(prefix)]
            radius_loc = fit_diffuser(frames, prior, cfg, cfg.seed + 70 + idx)
            radius_fits[str(radius)] = {
                "estimate": (list(radius_loc.estimate)
                             if radius_loc.estimate else None),
                "sigma_radius_m": radius_loc.sigma_radius_m,
                "aspect_span_deg": radius_loc.aspect_span_deg,
                "n_inliers": radius_loc.n_inliers,
                "fallback": radius_loc.fallback,
            }
            if not radius_loc.fallback and radius_loc.estimate:
                radius_locations.append(radius_loc)

        estimate, consensus_sigma = uncertainty_weighted_estimate(
            radius_locations)
        valid_radius_estimates = [radius_loc.estimate
                                  for radius_loc in radius_locations]
        confirmation_spread = None
        if estimate and valid_radius_estimates:
            confirmation_spread = max(dist2(estimate, xy)
                                      for xy in valid_radius_estimates)
        localization_confirmed = bool(
            not loc.fallback and estimate
            and len(valid_radius_estimates) >= 2
            and confirmation_spread is not None
            and confirmation_spread <= 5.0)
        sonar_visible = localization_confirmed

        # Robustness audit: rerun the same non-oracle residual evidence with
        # five plausible chart priors. Ground truth is not used by these fits.
        prior_offsets = [(0.0, 0.0), (-4.0, 0.0), (4.0, 0.0),
                         (0.0, -4.0), (0.0, 4.0)]
        robustness_trials = []
        for idx, (dx, dy) in enumerate(prior_offsets):
            test_prior = (prior[0] + dx, prior[1] + dy)
            test_radius_locations = []
            for r_idx, radius in enumerate(radii):
                prefix = f"r{int(radius):02d}_"
                frames = [frame for key, frame in residuals.items()
                          if key.startswith(prefix)]
                test_radius_locations.append(fit_diffuser(
                    frames, test_prior, cfg,
                    cfg.seed + 170 + idx * 10 + r_idx))
            test_estimate, test_sigma = uncertainty_weighted_estimate(
                test_radius_locations)
            test_fallback = test_estimate is None
            test_inliers = sum(loc_.n_inliers or 0
                               for loc_ in test_radius_locations)
            test_aspect = min((loc_.aspect_span_deg or 0.0)
                              for loc_ in test_radius_locations)
            robustness_trials.append({
                "prior": list(test_prior),
                "estimate": list(test_estimate) if test_estimate else None,
                "fallback": test_fallback,
                "sigma_radius_m": test_sigma,
                "aspect_span_deg": test_aspect,
                "n_inliers": test_inliers,
            })
        locate_payload = {
            "sensor_concept": "Omniscan 450 FS forward-looking imaging sonar",
            "prior": prior, "ring_radii_m": radii,
            "ring_poses": len(ring), "residual_contacts": loc_ncontacts,
            "method": ("pose-matched background subtraction + independent "
                       "multi-radius diffuser-line fits + inverse-uncertainty "
                       "consensus + confirmation pass"),
            "estimate": list(estimate) if estimate else None,
            "axis_deg": loc.axis_deg, "n_inliers": loc.n_inliers,
            "sigma_radius_m": consensus_sigma,
            "aspect_span_deg": loc.aspect_span_deg, "fallback": loc.fallback,
            "localization_confirmed": localization_confirmed,
            "confirmation_limit_m": 5.0,
            "confirmation_spread_m": confirmation_spread,
            "per_radius_fits": radius_fits,
            "prior_perturbation_trials": robustness_trials,
            "background_only_estimate": (list(bg_loc.estimate)
                                         if bg_loc.estimate else None),
        }
        (run_dir / "locate_result.json").write_text(
            json.dumps(locate_payload, indent=2), encoding="utf-8")
        if not sonar_visible:
            print("[custom-mission] WARNING: LOCATE fell back; anchoring survey "
                  "at the prior (NOT valid sonar-localization evidence).")
        else:
            print(f"[custom-mission] CONFIRMED SONAR LOCATE: estimate {estimate} "
                  f"({loc_ncontacts} residual contacts; multi-radius spread "
                  f"{confirmation_spread:.2f} m)")
        # The line estimator returns the physical diffuser midpoint. The scene
        # chart origin and plume coordinate are the diffuser start, so apply
        # the documented half-length offset along the chart axis. This uses
        # only known design geometry, never simulation truth.
        axis_rad = math.radians(cfg.outfall.axis_deg)
        half_diffuser = 0.5 * OutfallSceneConfig().diffuser_length_m
        survey_anchor = (
            (estimate[0] - half_diffuser * math.cos(axis_rad),
             estimate[1] - half_diffuser * math.sin(axis_rad))
            if sonar_visible else prior)
        locate_payload["derived_diffuser_start_estimate"] = list(survey_anchor)

        # ---- 7. build hazard field + drive to a safe start --------------- #
        field = HazardField.from_outfall(
            survey_anchor, cfg_cal.outfall.axis_deg, OutfallSceneConfig(),
            lambda x, y: float(terrain.z(x, y)),
            SafeNavConfig(clearance_m=args.clearance, min_altitude_m=1.0))
        # descend from above/away: park the ROV high over the box centre
        safe_start = Waypoint(start[0], start[1], float(terrain.z(*start[:2])) + 8.0)
        print("[custom-mission] repositioning ROV to a safe start...")
        drive_to(backend, safe_start)

        # ---- 7b. BASELINE + adaptive SURVEY, IN-ENGINE, collision-safe --- #
        print(f"[custom-mission] in-engine survey (budget {args.budget:.0f} m, "
              f"standoff {args.clearance:.1f} m)...")
        with MissionLogger(run_dir) as logger:
            runner = create_mission(
                cfg_cal, planner_name="adaptive", logger=logger,
                backend=backend, estimate_override=survey_anchor,
                hazard_field=field)
            result = runner.run()
        collisions = runner._collision_count
        detours = runner._detours
        min_clear = (None if runner._min_structure_clearance_m == float("inf")
                     else round(runner._min_structure_clearance_m, 2))
        print(f"[custom-mission] survey done: {len(result.samples)} samples, "
              f"budget {result.budget.used_m:.0f} m, collisions {collisions}, "
              f"detours {detours}, min clearance {min_clear} m")
    finally:
        backend.close()

    if result is None:
        return fail("mission did not run")

    # ---- 8. evaluation (ground truth allowed here only) ------------------ #
    plume = runner.plume
    grid = EvalGrid(cfg_cal.survey, plume.seabed_z, cfg_cal.compliance.eval_altitude_m)
    truth = plume.ground_truth(grid.points, t=0.0)
    mean, std = runner.mapper.predict(grid.points)
    bed_out = float(plume.seabed_z(cfg_cal.outfall.x, cfg_cal.outfall.y))
    ambient_bottom = float(plume.ambient_salinity(bed_out))
    threshold = boundary_salinity_psu(cfg_cal, plume)
    true_xy = plume.outfall_xy()
    axis_rad = math.radians(cfg_cal.outfall.axis_deg)
    half_diffuser = 0.5 * OutfallSceneConfig().diffuser_length_m
    diffuser_centre = (
        cfg_cal.outfall.x + half_diffuser * math.cos(axis_rad),
        cfg_cal.outfall.y + half_diffuser * math.sin(axis_rad))
    verdict = evaluate_compliance(mean, std, grid, true_xy, cfg_cal.compliance, ambient_bottom)
    gt_verdict = evaluate_compliance(truth, None, grid, true_xy, cfg_cal.compliance, ambient_bottom)
    metrics = compute_metrics(mean, truth, grid, result.samples, threshold, plume=plume)
    screening = screen(verdict, cfg_cal.compliance)
    outcome = screening_outcome(screening, gt_verdict.compliant)
    loc_error_centre = (dist2(estimate, diffuser_centre) if estimate else float("nan"))
    loc_error_origin = dist2(survey_anchor,
                             (cfg_cal.outfall.x, cfg_cal.outfall.y))

    # Post-hoc evaluation only: attach truth errors after every localization
    # decision has already been made and frozen.
    robust_errors = []
    for trial in locate_payload["prior_perturbation_trials"]:
        trial["posthoc_error_m_vs_diffuser_centre"] = (
            round(dist2(trial["estimate"], diffuser_centre), 3)
            if trial["estimate"] and not trial["fallback"] else None)
        if trial["posthoc_error_m_vs_diffuser_centre"] is not None:
            robust_errors.append(trial["posthoc_error_m_vs_diffuser_centre"])
    for radius_fit in locate_payload["per_radius_fits"].values():
        radius_fit["posthoc_error_m_vs_diffuser_centre"] = (
            round(dist2(radius_fit["estimate"], diffuser_centre), 3)
            if radius_fit["estimate"] and not radius_fit["fallback"] else None)
    locate_payload["posthoc_ground_truth_diffuser_centre"] = list(diffuser_centre)
    locate_payload["posthoc_error_m_vs_diffuser_centre"] = round(
        loc_error_centre, 3) if math.isfinite(loc_error_centre) else None
    locate_payload["robustness_summary"] = {
        "valid_trials": len(robust_errors),
        "total_trials": len(locate_payload["prior_perturbation_trials"]),
        "median_error_m": (round(float(np.median(robust_errors)), 3)
                           if robust_errors else None),
        "max_error_m": (round(float(np.max(robust_errors)), 3)
                        if robust_errors else None),
    }
    (run_dir / "locate_result.json").write_text(
        json.dumps(locate_payload, indent=2), encoding="utf-8")

    save_samples_csv(result.samples, result.budget_at_sample, run_dir / "samples.csv")
    np.savez_compressed(
        run_dir / "plume_maps.npz",
        mean=grid.reshape(mean), std=grid.reshape(std), truth=grid.reshape(truth),
        X=grid.X, Y=grid.Y, Z=grid.Z,
        trajectory=np.asarray(result.trajectory, dtype=float))
    fig1 = plot_truth_vs_reconstruction(
        grid, truth, mean, std, result.samples, result.trajectory,
        true_xy, cfg_cal.compliance.mixing_zone_radius_m, threshold,
        run_dir / "map_truth_vs_reconstruction.png",
        title="PFH2026 custom-engine IN-ENGINE mission (collision-safe)")
    fig2 = plot_compliance_map(
        grid, mean, threshold, true_xy, cfg_cal.compliance.mixing_zone_radius_m,
        run_dir / "map_compliance.png", worst_point=verdict.worst_point,
        title=f"Screening: {screening.label}")

    extra = {
        "custom_engine_used": True,
        "in_engine_survey": True,
        "spawned_outfall_sonar_visible": sonar_visible,
        "localized_by_sonar": bool(sonar_visible and estimate is not None),
        "locate_backend": "holoocean_custom (native simulated ImagingSonar, background subtraction)",
        "survey_backend": "holoocean_custom (BlueROV2 driven in-engine, collision-safe)",
        "plume_note": "analytic simulation surrogate sampled along the engine trajectory",
        "raw_sonar_contacts": loc_ncontacts,
        "consensus_estimate": list(estimate) if estimate else None,
        "localization_confirmed": localization_confirmed,
        "localization_confirmation_spread_m": confirmation_spread,
        "localization_robustness": locate_payload["robustness_summary"],
        "mission_detection_events": len(result.detections),
        "localization_error_m_vs_diffuser_centre": round(loc_error_centre, 2),
        "derived_origin_error_m": round(loc_error_origin, 2),
        "sonar_estimate": list(estimate) if estimate else None,
        "derived_diffuser_start_estimate": list(survey_anchor),
        "chart_prior": list(prior),
        "collision_safe_nav": True,
        "collisions": collisions,
        "safe_detours": detours,
        "min_structure_clearance_m": min_clear,
        "standoff_m": args.clearance,
        "screening": screening.state.value,
        "screening_outcome_vs_gt": outcome,
        "gt_verdict": gt_verdict.label,
        "scene_components_ok": n_ok,
        "terrain_plane_rmse_m": round(fit.rmse_m, 3),
        "rmse_plume": round(metrics.rmse_plume, 4),
        "boundary_f1": round(metrics.boundary_f1, 3),
        "boundary_iou": round(metrics.boundary_iou, 3),
        "coverage_frac": round(metrics.coverage_frac, 3),
        "useful_sample_frac": round(metrics.in_plume_frac, 3),
    }
    save_result_summary(result, run_dir / "summary.json", extra=extra)
    report = render_html_report(
        run_dir / "report.html", cfg_cal, result, verdict, gt_verdict, metrics,
        figures={"Ground truth vs reconstruction": fig1, "Compliance map": fig2},
        extra=extra, screening=screening)

    print(f"[custom-mission] IN-ENGINE survey: {len(result.samples)} samples, "
          f"collisions {collisions}, detours {detours}, "
          f"min clearance {min_clear} m (standoff {args.clearance} m)")
    print(f"[custom-mission] sonar-localized: {sonar_visible} | "
          f"error vs diffuser centre {loc_error_centre:.2f} m")
    print(f"[custom-mission] screening: {screening.label} (vs GT: {outcome})")
    print(f"[custom-mission] report: {report}")
    (run_dir / "CUSTOM_MISSION_OK").write_text(json.dumps(extra, indent=2),
                                               encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

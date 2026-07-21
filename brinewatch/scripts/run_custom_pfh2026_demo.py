"""PFH 2026 CUSTOM-ENGINE scientific mission (Demo 1).

End-to-end BlueROV2 mission in the custom HoloOcean fork, locating the ACTUAL
spawned outfall by native simulated (non-oracle) sonar (runtime octree rebuild), then surveying and
mapping the brine plume.

Stages (single fork-engine session; the engine must already be running, see
scripts/launch_custom_engine.py):
 1. attach (custom backend, auto-discovered in-project engine);
 2. terrain-calibration probe over the survey box;
 3. BASELINE sonar ring around the chart prior -- NO outfall yet
    (pre-installation baseline pass);
 4. spawn the multiport outfall (SpawnAsset -> octree rebuild);
 5. INSPECTION sonar ring at the SAME poses (outfall present);
 6. LOCATE: pose-matched background subtraction isolates the outfall from
    native clutter -> robust consensus estimate. No ground truth. If it
    falls back, the run is flagged NOT sonar-localized (disqualifying).
 7. full mission BASELINE + adaptive SURVEY on the VALIDATED KINEMATIC model,
    anchored at the sonar ESTIMATE, sampling the synthetic plume + CTD (the
    custom engine is released after LOCATE; driving the real ROV through the
    spawned structure collides -- see run_custom_holoocean_mission.py for the
    collision-safe in-HoloOcean survey);
 8. GP reconstruction, three-state screening, report; post-mission
    evaluation (ground truth used ONLY here): localization error, metrics.

This is honestly a "custom-HoloOcean sonar LOCATE + kinematic survey" demo.
The genuinely end-to-end in-HoloOcean mission (motion + sensing in the engine)
is scripts/run_custom_holoocean_mission.py.

Usage (engine first):
    python scripts/launch_custom_engine.py --clear-cache        # terminal 1
    python scripts/run_custom_pfh2026_demo.py                   # terminal 2
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
from brinewatch.perception.sonar_background_locator import (
    BackgroundLocatorConfig, SonarBackgroundLocator)
from brinewatch.simulation import make_backend
from brinewatch.utils.config import load_config, save_config
from brinewatch.utils.geometry import dist2
from brinewatch.utils.logging_utils import (
    MissionLogger, make_run_dir, save_result_summary, save_samples_csv)
from brinewatch.visualization.plots import (
    plot_compliance_map, plot_truth_vs_reconstruction)
from brinewatch.visualization.report import render_html_report


def fail(msg: str) -> int:
    print(f"[custom-demo] FATAL: {msg}")
    return 1


def ring_poses(center, radius, n, bed_fn, height=3.0):
    """n poses on a ring around ``center``, each looking inward at it."""
    cx, cy = center
    poses = []
    for k in range(n):
        a = 2 * math.pi * k / n
        px, py = cx + radius * math.cos(a), cy + radius * math.sin(a)
        yaw = math.degrees(math.atan2(cy - py, cx - px))
        pz = float(bed_fn(px, py)) + height
        poses.append((f"r{int(radius):02d}_k{k:02d}", px, py, pz, yaw))
    return poses


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default=str(REPO_ROOT / "configs" / "pfh2026_custom.yaml"))
    ap.add_argument("--out", default=str(REPO_ROOT / "outputs"))
    ap.add_argument("--ring-radius", type=float, default=22.0)
    ap.add_argument("--ring-poses", type=int, default=18)
    ap.add_argument("--reuse-locate", default=None,
                    help="complete the mission from a prior run dir's real "
                         "custom-engine sonar LOCATE (frames + estimate), "
                         "skipping the engine")
    args = ap.parse_args()

    cfg = load_config(args.config)
    if cfg.backend.name != "holoocean_custom":
        return fail("this demo requires backend.name: holoocean_custom")
    if cfg.locator.mode != "sonar":
        return fail("this demo requires locator.mode: sonar")
    if cfg.locator.prior_x is None or cfg.locator.prior_y is None:
        return fail("this demo requires an explicit chart prior")

    run_dir = make_run_dir(args.out, cfg.name)
    print(f"[custom-demo] run dir: {run_dir}")
    save_config(cfg, run_dir / "config_used.yaml")
    prior = (float(cfg.locator.prior_x), float(cfg.locator.prior_y))

    from brinewatch.utils.terrain import TerrainMap

    sonar_visible = False
    estimate = None
    loc_ncontacts = 0
    loc_aspect = 0.0
    n_ok = 0

    if args.reuse_locate:
        # Complete the mission from a prior run's REAL custom-engine sonar
        # LOCATE (frames + estimate), skipping the engine. Used when the
        # engine is flaky between runs; the sonar evidence is unchanged.
        import shutil
        src = Path(args.reuse_locate)
        print(f"[custom-demo] reusing sonar LOCATE from {src}")
        lr = json.loads((src / "locate_result.json").read_text(encoding="utf-8"))
        estimate = tuple(lr["estimate"]) if lr.get("estimate") else None
        sonar_visible = not lr.get("fallback", True)
        loc_ncontacts = lr.get("residual_contacts", 0)
        loc_aspect = lr.get("aspect_span_deg", 0.0)
        terrain = TerrainMap.from_npz(src / "terrain.npz")
        fit = terrain.fit_plane(robust=True)
        cfg_cal = dataclasses.replace(cfg, environment=dataclasses.replace(
            cfg.environment, seabed_z0=fit.z0,
            seabed_slope_x=fit.slope_x, seabed_slope_y=fit.slope_y))
        try:
            man = json.loads((src / "scene_manifest.json").read_text(encoding="utf-8"))
            comps = man.get("components", man if isinstance(man, list) else [])
            n_ok = sum(1 for c in comps if c.get("ok", True))
        except Exception:
            n_ok = 0
        for f in ("locate_result.json", "locate_baseline_frames.npz",
                  "locate_inspection_frames.npz", "scene_manifest.json",
                  "terrain.npz"):
            if (src / f).is_file():
                shutil.copy2(src / f, run_dir / f)
        print(f"[custom-demo] reused estimate {estimate} "
              f"(sonar_visible={sonar_visible}, contacts={loc_ncontacts})")
    else:
        start = (0.5 * (cfg.survey.x_min + cfg.survey.x_max),
                 0.5 * (cfg.survey.y_min + cfg.survey.y_max),
                 cfg.environment.seabed_z0 + 8.0)
        backend = make_backend("holoocean_custom", cfg.backend, cfg.environment,
                               cfg.outfall, start, seed=cfg.seed + 41)
        try:
            # ---- 2. terrain probe ---------------------------------------- #
            upstream = math.radians(cfg.environment.current_dir_deg + 180.0)
            builder = backend.scene_builder(upstream_dir_rad=upstream)
            xs = np.linspace(cfg.survey.x_min + 8.0, cfg.survey.x_max - 8.0, 6)
            ys = np.linspace(cfg.survey.y_min + 8.0, cfg.survey.y_max - 8.0, 5)
            terrain = builder.probe_terrain(reference_bed_z=cfg.environment.seabed_z0,
                                            xs=xs, ys=ys)
            terrain.save_npz(run_dir / "terrain.npz")
            fit = terrain.fit_plane(robust=True)
            print(f"[custom-demo] terrain plane z0={fit.z0:.2f} rmse={fit.rmse_m:.2f} m")
            cfg_cal = dataclasses.replace(cfg, environment=dataclasses.replace(
                cfg.environment, seabed_z0=fit.z0,
                seabed_slope_x=fit.slope_x, seabed_slope_y=fit.slope_y))

            def bed_fn(x, y):
                return terrain.z(x, y)

            ring = ring_poses(prior, args.ring_radius, args.ring_poses, bed_fn)

            # ---- 3. BASELINE sonar ring (no outfall) --------------------- #
            print(f"[custom-demo] baseline sonar ring ({len(ring)} poses)...")
            baseline = {}
            for key, px, py, pz, yaw in ring:
                fr = backend.capture_sonar_at(px, py, pz, yaw)
                if fr is not None:
                    baseline[key] = fr
            print(f"[custom-demo] baseline captured {len(baseline)}/{len(ring)}")

            # ---- 4. spawn outfall (SpawnAsset -> octree rebuild) --------- #
            components = builder.build()
            builder.save_manifest(run_dir / "scene_manifest.json")
            n_ok = sum(1 for c in components if c.ok)
            backend._tick_n(45, backend._hold_command())  # dirty + rebuild
            print(f"[custom-demo] spawned outfall: {n_ok} components")

            # ---- 5. INSPECTION sonar ring (same poses) ------------------- #
            print("[custom-demo] inspection sonar ring...")
            live = {}
            for key, px, py, pz, yaw in ring:
                fr = backend.capture_sonar_at(px, py, pz, yaw)
                if fr is not None:
                    live[key] = fr
            print(f"[custom-demo] inspection captured {len(live)}/{len(ring)}")

            np.savez_compressed(run_dir / "locate_baseline_frames.npz",
                                **{k: v.image for k, v in baseline.items()})
            np.savez_compressed(run_dir / "locate_inspection_frames.npz",
                                **{k: v.image for k, v in live.items()})

            # ---- 6. background-subtraction LOCATE (no GT) ---------------- #
            blc = SonarBackgroundLocator(BackgroundLocatorConfig(
                prior_xy=prior, prior_gate_m=30.0))
            for key in sorted(set(baseline) & set(live)):
                loc_ncontacts += blc.ingest(baseline[key], live[key])
            loc = blc.localize()
            sonar_visible = not loc.fallback
            estimate = loc.estimate
            loc_aspect = loc.aspect_span_deg
            (run_dir / "locate_result.json").write_text(json.dumps({
                "prior": prior, "ring_radius_m": args.ring_radius,
                "ring_poses": len(ring), "residual_contacts": loc_ncontacts,
                "estimate": list(estimate) if estimate else None,
                "core_size": loc.core_size, "aspect_span_deg": loc.aspect_span_deg,
                "fallback": loc.fallback}, indent=2), encoding="utf-8")
            if sonar_visible:
                print(f"[custom-demo] SONAR LOCATE: estimate {estimate} "
                      f"({loc_ncontacts} residual contacts, aspect {loc_aspect} deg)")
            else:
                print("[custom-demo] WARNING: LOCATE fell back (no sonar consensus). "
                      "NOT valid sonar-localization evidence; survey uses the prior.")
        finally:
            backend.close()

    # ---- 7. survey on the validated kinematic model, anchored at the ------ #
    #        real custom-engine sonar estimate. The plume/CTD/GP stack is
    #        synthetic in every BrineWatch demo; driving the real ROV through
    #        the spawned structure risks collisions, so the survey uses the
    #        collision-free kinematic backend (clearly labelled). The sonar
    #        LOCATE above is the real custom-engine evidence.
    survey_anchor = estimate if sonar_visible else prior
    with MissionLogger(run_dir) as logger:
        runner = create_mission(
            cfg_cal, backend_name="kinematic", logger=logger,
            estimate_override=survey_anchor)
        result = runner.run()

    # ---- 8. evaluation (ground truth allowed here only) ------------------ #
    plume = runner.plume
    grid = EvalGrid(cfg_cal.survey, plume.seabed_z, cfg_cal.compliance.eval_altitude_m)
    truth = plume.ground_truth(grid.points, t=0.0)
    mean, std = runner.mapper.predict(grid.points)

    bed_out = float(plume.seabed_z(cfg_cal.outfall.x, cfg_cal.outfall.y))
    ambient_bottom = float(plume.ambient_salinity(bed_out))
    threshold = boundary_salinity_psu(cfg_cal, plume)
    true_xy = plume.outfall_xy()
    # the sonar aims at the diffuser/riser field (strongest returns) ~ the
    # diffuser centre, offset +x from the scene origin by half the diffuser
    from brinewatch.simulation.outfall_scene import OutfallSceneConfig
    diffuser_centre = (cfg_cal.outfall.x + OutfallSceneConfig().diffuser_length_m / 2.0,
                       cfg_cal.outfall.y)

    verdict = evaluate_compliance(mean, std, grid, true_xy, cfg_cal.compliance, ambient_bottom)
    gt_verdict = evaluate_compliance(truth, None, grid, true_xy, cfg_cal.compliance, ambient_bottom)
    metrics = compute_metrics(mean, truth, grid, result.samples, threshold, plume=plume)
    screening = screen(verdict, cfg_cal.compliance)
    outcome = screening_outcome(screening, gt_verdict.compliant)

    loc_error_centre = (dist2(estimate, diffuser_centre) if estimate else float("nan"))
    loc_error_origin = (dist2(estimate, (cfg_cal.outfall.x, cfg_cal.outfall.y))
                        if estimate else float("nan"))

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
        title="PFH2026 custom-engine demo - sonar-localized outfall")
    fig2 = plot_compliance_map(
        grid, mean, threshold, true_xy, cfg_cal.compliance.mixing_zone_radius_m,
        run_dir / "map_compliance.png", worst_point=verdict.worst_point,
        title=f"Screening: {screening.label}")

    extra = {
        "custom_engine_used": True,
        "spawned_outfall_sonar_visible": sonar_visible,
        "sonar_octree_refreshed": True,
        "localized_by_sonar": bool(sonar_visible and estimate is not None),
        "locate_backend": "holoocean_custom (native simulated ImagingSonar, background subtraction)",
        "survey_backend": "kinematic (validated model; collision-free), anchored at the sonar estimate",
        "acoustic_target": "the ACTUAL spawned multiport outfall (custom fork)",
        # three distinct quantities, kept separate:
        "raw_sonar_contacts": loc_ncontacts,          # detector-level residual contacts
        "consensus_estimate": list(estimate) if estimate else None,  # single mode-cluster fix
        "mission_detection_events": len(result.detections),  # Detection objects logged
        "aspect_span_deg": loc_aspect,
        "localization_error_m_vs_diffuser_centre": round(loc_error_centre, 2),
        "localization_error_m_vs_scene_origin": round(loc_error_origin, 2),
        "sonar_estimate": list(estimate) if estimate else None,
        "chart_prior": list(prior),
        "screening": screening.state.value,
        "screening_outcome_vs_gt": outcome,
        "gt_verdict": gt_verdict.label,
        "scene_components_ok": n_ok,
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

    print(f"[custom-demo] mission: {len(result.samples)} samples, "
          f"budget {result.budget.used_m:.0f}/{result.budget.max_distance_m:.0f} m, "
          f"collisions {result.__dict__.get('_collision_count', '?')}")
    print(f"[custom-demo] sonar-localized: {sonar_visible} | "
          f"error vs diffuser centre {loc_error_centre:.2f} m")
    print(f"[custom-demo] screening: {screening.label} (vs GT: {outcome}) | "
          f"rmse_plume {metrics.rmse_plume:.3f}")
    print(f"[custom-demo] report: {report}")
    (run_dir / "CUSTOM_DEMO_OK").write_text(json.dumps(extra, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

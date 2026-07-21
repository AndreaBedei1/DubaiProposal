"""3-D volumetric brine-plume reconstruction from a multi-altitude survey.

Dense brine forms a near-bottom layer, so a single near-bottom pass only sees
one slice of it. Here the BlueROV2 surveys the site at several altitude bands
above the seabed; all CTD samples feed ONE anisotropic 3-D GP, which is
reconstructed on a terrain-following x-y-z grid. Outputs: horizontal +
vertical slices, a configurable iso-surface, and plume area / volume /
uncertainty estimates. The near-bottom compliance layer (screening) is
retained because it is the environmentally relevant one.

Kinematic backend by default (fast, reproducible); the plume is the analytic
SIMULATION SURROGATE. Reconstruction error is scored against it for evaluation.

    python scripts/run_volumetric_mission.py [--config configs/mission_default.yaml]
                                             [--planner adaptive] [--altitudes 1.5 3.5 6.0]
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from brinewatch.mapping.gp_mapper import GPMapper
from brinewatch.mapping.volumetric import (
    VolumetricConfig, VolumetricGrid, metrics, plot_isosurface_3d, plot_slices,
    reconstruct)
from brinewatch.mission.runner import boundary_salinity_psu, create_mission
from brinewatch.plume.model import BrinePlume
from brinewatch.utils.config import load_config
from brinewatch.utils.logging_utils import make_run_dir


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default=str(REPO / "configs" / "mission_default.yaml"))
    ap.add_argument("--planner", default="adaptive")
    ap.add_argument("--altitudes", type=float, nargs="+", default=[1.5, 3.5, 6.0])
    ap.add_argument("--out", default=str(REPO / "outputs"))
    args = ap.parse_args()

    cfg = load_config(args.config)
    run_dir = make_run_dir(args.out, f"volumetric_{args.planner}")
    print(f"[volumetric] run dir: {run_dir}")

    plume = BrinePlume(cfg.environment, cfg.outfall, cfg.plume)
    threshold = boundary_salinity_psu(cfg, plume)

    # split the travel budget across altitude bands; each band is one survey
    band_budget = cfg.budget.max_distance_m / len(args.altitudes)
    all_samples = []
    trajectory = []
    per_band = []
    for i, alt in enumerate(args.altitudes):
        band_cfg = dataclasses.replace(
            cfg,
            survey=dataclasses.replace(cfg.survey, altitude_m=alt),
            budget=dataclasses.replace(cfg.budget, max_distance_m=band_budget),
            seed=cfg.seed + i)
        runner = create_mission(band_cfg, planner_name=args.planner)
        result = runner.run()
        all_samples.extend(result.samples)
        if trajectory:
            trajectory.append([np.nan, np.nan, np.nan, np.nan])  # break between band polylines
        trajectory.extend([list(p) for p in result.trajectory])
        per_band.append({"altitude_m": alt, "samples": len(result.samples),
                         "budget_used_m": round(result.budget.used_m, 1)})
        print(f"[volumetric] band {alt:.1f} m: {len(result.samples)} samples")

    # one 3-D GP over ALL samples (anisotropic: long xy, short z)
    mapper = GPMapper(cfg.gp, plume.ambient_salinity, seed=cfg.seed + 31)
    mapper.add_samples(all_samples)

    vcfg = VolumetricConfig()
    grid = VolumetricGrid(cfg.survey, plume.seabed_z, vcfg)
    mean_vol, std_vol = reconstruct(mapper, grid)
    truth_vol = grid.reshape(plume.ground_truth(grid.points, t=0.0))

    m = metrics(mean_vol, std_vol, grid, threshold)
    m_truth = metrics(truth_vol, np.zeros_like(truth_vol), grid, threshold)

    # reconstruction accuracy vs the surrogate truth
    err = mean_vol - truth_vol
    rmse = float(np.sqrt(np.mean(err ** 2)))
    mae = float(np.mean(np.abs(err)))
    # volumetric boundary IoU (connected plume bodies)
    from brinewatch.mapping.volumetric import plume_body_mask
    pm, tm = plume_body_mask(mean_vol, threshold), plume_body_mask(truth_vol, threshold)
    inter = int((pm & tm).sum())
    union = int((pm | tm).sum())
    iou = inter / union if union else 1.0

    plot_slices(mean_vol, std_vol, grid, threshold,
                run_dir / "volumetric_slices.png",
                title=f"3-D plume reconstruction ({args.planner}, "
                      f"{len(all_samples)} samples, {len(args.altitudes)} altitudes)",
                truth_vol=truth_vol)
    plot_isosurface_3d(mean_vol, grid, threshold,
                       run_dir / "volumetric_isosurface.png",
                       title=f"Plume iso-surface (salinity ≥ {threshold:.2f} PSU) "
                             f"— est. volume {m.plume_volume_m3:.0f} m³",
                       trajectory=np.asarray(trajectory, dtype=float))

    np.savez_compressed(run_dir / "volume.npz", mean=mean_vol, std=std_vol,
                        truth=truth_vol, X=grid.X, Y=grid.Y, Z=grid.Z,
                        alts=grid.alts, threshold=threshold)
    summary = {
        "planner": args.planner, "altitudes_m": args.altitudes,
        "n_samples": len(all_samples), "per_band": per_band,
        "threshold_psu": round(threshold, 3),
        "reconstruction": {"rmse_psu": round(rmse, 4), "mae_psu": round(mae, 4),
                           "volume_iou": round(iou, 3)},
        "estimated": dataclasses.asdict(m),
        "ground_truth": dataclasses.asdict(m_truth),
        "grid": {"nx": vcfg.nx, "ny": vcfg.ny, "nz": vcfg.nz,
                 "z_above_bed_max_m": vcfg.z_above_bed_max_m},
        "plume_note": "analytic simulation surrogate, not CFD ground truth",
    }
    (run_dir / "volumetric_summary.json").write_text(json.dumps(summary, indent=2),
                                                     encoding="utf-8")
    print(f"[volumetric] plume volume {m.plume_volume_m3:.0f} m³ "
          f"(truth {m_truth.plume_volume_m3:.0f}), bottom area "
          f"{m.plume_area_bottom_m2:.0f} m² (truth {m_truth.plume_area_bottom_m2:.0f})")
    print(f"[volumetric] reconstruction rmse {rmse:.3f} PSU, volume IoU {iou:.2f}")
    print(f"[volumetric] DONE -> {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

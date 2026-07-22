"""Competition comparison: sparse fixed stations, lawnmower and BrineWatch.

All strategies see the same analytic plume surrogate, sensor noise, sample
count, survey box and maximum travel budget.  The fixed-station strategy uses
24 spatial stations in a sparse 4 x 6 grid; if more than 24 readings are
requested, they are transparent replicate readings at those same stations.
The two ROV strategies are downsampled uniformly to the same reading count.

This is a simulation decision-support comparison, not a claim that BrineWatch
replaces accredited/manual monitoring.
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import json
import math
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from brinewatch.evaluation.compliance import evaluate_compliance
from brinewatch.evaluation.metrics import compute_metrics
from brinewatch.evaluation.screening import screen, screening_outcome
from brinewatch.mapping.gp_mapper import GPMapper
from brinewatch.mapping.grid_map import EvalGrid
from brinewatch.mission.runner import boundary_salinity_psu, create_mission
from brinewatch.plume.model import BrinePlume
from brinewatch.utils.config import load_config
from brinewatch.utils.logging_utils import make_run_dir
from brinewatch.utils.types import CTDSample


def _fixed_station_samples(cfg, plume, count: int, seed: int):
    """Sparse 4 x 6 station grid, visited boustrophedon-style."""
    xs = np.linspace(cfg.survey.x_min + 3.0, cfg.survey.x_max - 3.0, 6)
    ys = np.linspace(cfg.survey.y_min + 4.0, cfg.survey.y_max - 4.0, 4)
    stations = []
    for j, y in enumerate(ys):
        row = list(xs if j % 2 == 0 else xs[::-1])
        stations.extend((float(x), float(y)) for x in row)

    rng = np.random.default_rng(cfg.seed + 500 + seed)
    samples = []
    travel = 0.0
    previous = None
    speed_mps = 0.6
    dwell_s = 45.0
    t = 0.0
    for i in range(count):
        x, y = stations[i % len(stations)]
        if previous is not None:
            leg = math.hypot(x - previous[0], y - previous[1])
            if travel + leg > cfg.budget.max_distance_m:
                # Preserve the hard budget: remaining readings are replicates
                # at the last reached certified-style station.
                x, y = previous
                leg = 0.0
            travel += leg
            t += leg / speed_mps
        z = float(plume.seabed_z(x, y)) + cfg.survey.altitude_m
        t += dwell_s
        samples.append(CTDSample(
            t=t, x=x, y=y, z=z,
            salinity_psu=float(plume.salinity(x, y, z, t))
                         + rng.normal(0.0, cfg.ctd.salinity_sigma_psu),
            temperature_c=float(plume.temperature(x, y, z, t))
                          + rng.normal(0.0, cfg.ctd.temperature_sigma_c),
            depth_m=max(0.0, -z) + rng.normal(0.0, cfg.ctd.depth_sigma_m)))
        previous = (x, y)
    return samples, travel, t


def _uniform_subset(samples, count: int):
    if len(samples) <= count:
        return list(samples)
    idx = np.linspace(0, len(samples) - 1, count).round().astype(int)
    return [samples[int(i)] for i in idx]


def _evaluate(strategy, seed, samples, travel_m, operating_s, cfg, plume,
              grid, truth, threshold, gt_verdict):
    mapper = GPMapper(cfg.gp, plume.ambient_salinity, seed=cfg.seed + 700 + seed)
    mapper.add_samples(samples)
    mean, std = mapper.predict(grid.points)
    true_xy = plume.outfall_xy()
    bed_out = float(plume.seabed_z(*true_xy))
    ambient_bottom = float(plume.ambient_salinity(bed_out))
    verdict = evaluate_compliance(mean, std, grid, true_xy, cfg.compliance,
                                  ambient_bottom)
    screening = screen(verdict, cfg.compliance)
    metrics = compute_metrics(mean, truth, grid, samples, threshold, plume=plume)
    true_mask = truth > threshold
    pred_mask = mean > threshold
    missed = float(np.count_nonzero(true_mask & ~pred_mask)
                   / max(1, np.count_nonzero(true_mask)))
    state_value = screening.state.value.lower()
    conclusive = state_value != "review"
    false_clear = bool(not gt_verdict.compliant
                       and state_value == "clear")
    false_exceedance = bool(gt_verdict.compliant
                            and state_value == "possible_exceedance")
    return {
        "strategy": strategy, "seed": seed, "n_samples": len(samples),
        "unique_sample_sites": len({(round(s.x, 2), round(s.y, 2))
                                    for s in samples}),
        "travel_distance_m": round(float(travel_m), 2),
        "approx_operating_time_min": round(float(operating_s) / 60.0, 2),
        "rmse_plume_psu": metrics.rmse_plume,
        "boundary_f1": metrics.boundary_f1,
        "boundary_iou": metrics.boundary_iou,
        "missed_plume_fraction": missed,
        "useful_sample_fraction": metrics.in_plume_frac,
        "mean_posterior_std_psu": float(np.mean(std)),
        "max_std_outside_psu": verdict.max_std_outside_psu,
        "prob_exceed_max": verdict.prob_exceed_max,
        "screening_state": state_value,
        "screening_outcome": screening_outcome(screening,
                                                gt_verdict.compliant),
        "conclusive": conclusive,
        "false_clear": false_clear,
        "false_exceedance": false_exceedance,
        "ground_truth_compliant": bool(gt_verdict.compliant),
    }


def _summarize(rows):
    summary = {}
    metric_names = [
        "n_samples", "unique_sample_sites", "travel_distance_m",
        "approx_operating_time_min", "rmse_plume_psu", "boundary_f1",
        "boundary_iou", "missed_plume_fraction", "useful_sample_fraction",
        "mean_posterior_std_psu", "max_std_outside_psu",
    ]
    for strategy in sorted({r["strategy"] for r in rows}):
        selected = [r for r in rows if r["strategy"] == strategy]
        n = len(selected)
        states = {state: sum(r["screening_state"] == state for r in selected)
                  for state in ("clear", "possible_exceedance", "review")}
        conclusive = [r for r in selected if r["conclusive"]]
        item = {
            "runs": n,
            "screening": {
                "clear_count": states["clear"],
                "clear_pct": 100.0 * states["clear"] / n,
                "possible_exceedance_count": states["possible_exceedance"],
                "possible_exceedance_pct": 100.0 * states["possible_exceedance"] / n,
                "review_count": states["review"],
                "review_pct": 100.0 * states["review"] / n,
                "conclusive_rate_pct": 100.0 * len(conclusive) / n,
                "accuracy_among_conclusive_pct": (100.0 * sum(
                    r["screening_outcome"] == "correct" for r in conclusive)
                    / len(conclusive) if conclusive else None),
                "false_clear_count": sum(r["false_clear"] for r in selected),
                "false_exceedance_count": sum(r["false_exceedance"] for r in selected),
                "probability_of_missing_exceedance_pct": 100.0 * sum(
                    r["false_clear"] for r in selected) / n,
                "abstention_review_rate_pct": 100.0 * states["review"] / n,
            },
        }
        for name in metric_names:
            values = np.asarray([r[name] for r in selected], dtype=float)
            item[name] = {"mean": float(values.mean()),
                          "std": float(values.std())}
        summary[strategy] = item
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default=str(
        REPO / "configs" / "pfh2026_flagship_demo.yaml"))
    ap.add_argument("--budget", type=float, default=300.0)
    ap.add_argument("--samples", type=int, default=48)
    ap.add_argument("--seeds", type=int, default=8)
    ap.add_argument("--out", default=str(REPO / "outputs"))
    args = ap.parse_args()

    cfg = load_config(args.config)
    cfg = dataclasses.replace(
        cfg, budget=dataclasses.replace(cfg.budget,
                                        max_distance_m=args.budget,
                                        checkpoints=(1.0,)))
    out = make_run_dir(args.out, "competition_comparison")
    plume = BrinePlume(cfg.environment, cfg.outfall, cfg.plume)
    grid = EvalGrid(cfg.survey, plume.seabed_z,
                    cfg.compliance.eval_altitude_m)
    truth = plume.ground_truth(grid.points, t=0.0)
    threshold = boundary_salinity_psu(cfg, plume)
    true_xy = plume.outfall_xy()
    ambient_bottom = float(plume.ambient_salinity(
        float(plume.seabed_z(*true_xy))))
    gt_verdict = evaluate_compliance(truth, None, grid, true_xy,
                                     cfg.compliance, ambient_bottom)

    rows = []
    for seed in range(args.seeds):
        fixed, travel, operating_s = _fixed_station_samples(
            cfg, plume, args.samples, seed)
        rows.append(_evaluate("sparse_fixed_stations", seed, fixed, travel,
                              operating_s, cfg, plume, grid, truth, threshold,
                              gt_verdict))
        for planner in ("lawnmower", "adaptive"):
            runner = create_mission(cfg, planner_name=planner,
                                    backend_name="kinematic",
                                    seed_offset=seed)
            try:
                result = runner.run()
            finally:
                runner.backend.close()
            samples = _uniform_subset(result.samples, args.samples)
            travel = float(result.budget.used_m)
            # Same conservative 0.6 m/s vehicle speed; rolling CT readings
            # need two seconds each rather than a 45-second station dwell.
            operating_s = travel / 0.6 + len(samples) * 2.0
            rows.append(_evaluate(planner, seed, samples, travel, operating_s,
                                  cfg, plume, grid, truth, threshold,
                                  gt_verdict))

    fields = list(rows[0])
    with (out / "comparison_records.csv").open("w", newline="",
                                                 encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    result = {
        "scenario": cfg.name,
        "scenario_note": ("demo-optimised analytic simulation surrogate; "
                          "not CFD or field truth"),
        "fairness": {
            "same_sample_count": args.samples,
            "same_max_travel_budget_m": args.budget,
            "same_survey_area": [cfg.survey.x_min, cfg.survey.x_max,
                                 cfg.survey.y_min, cfg.survey.y_max],
            "same_sensor_noise_psu": cfg.ctd.salinity_sigma_psu,
            "fixed_station_design": "24 stations (4 x 6), then replicates",
            "operating_time_assumptions": {
                "vehicle_speed_mps": 0.6,
                "fixed_station_dwell_s": 45.0,
                "rolling_rov_reading_s": 2.0,
            },
        },
        "ground_truth": "FAIL" if not gt_verdict.compliant else "PASS",
        "summary": _summarize(rows),
    }
    (out / "comparison_summary.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result["summary"], indent=2))
    print(f"[comparison] output: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

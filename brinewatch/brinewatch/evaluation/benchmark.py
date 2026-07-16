"""Equal-budget benchmark: lawnmower vs adaptive.

For each (planner, seed) a full mission is run from the same config; at every
budget checkpoint a fresh GP is refit on only the samples collected within
that budget, and reconstruction metrics plus the compliance verdict are
computed against the analytic ground truth (evaluated at t=0; tide-induced
motion between sampling and evaluation is part of the reconstruction
challenge, see docs/assumptions.md). Records are flat dicts, saved as CSV,
with a per-planner/per-checkpoint mean/std summary saved as JSON.
"""
from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

import numpy as np

from ..mapping.gp_mapper import GPMapper
from ..mapping.grid_map import EvalGrid
from ..mission.runner import boundary_salinity_psu, create_mission
from ..utils.config import MissionConfig
from .compliance import evaluate_compliance
from .metrics import compute_metrics
from .screening import screen, screening_outcome

RECORD_KEYS = [
    "planner", "seed", "checkpoint_frac", "budget_m", "n_samples",
    "rmse_all", "rmse_plume", "mae_all", "boundary_f1", "boundary_iou",
    "coverage_frac", "in_plume_frac", "compliant", "gt_compliant",
    "verdict_correct", "max_exceedance_psu", "prob_exceed_max",
    "max_std_outside_psu", "screening_state", "screening_outcome",
]

SUMMARY_METRICS = [
    "rmse_all", "rmse_plume", "mae_all", "boundary_f1", "boundary_iou",
    "coverage_frac", "in_plume_frac", "n_samples",
]


@dataclass
class BenchmarkResult:
    records: List[Dict[str, Any]] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)


def run_benchmark(
    cfg: MissionConfig,
    out_dir: Union[str, Path],
    planners: Sequence[str] = ("lawnmower", "adaptive"),
    seeds: Sequence[int] = (0, 1, 2, 3, 4),
    backend: Optional[str] = "kinematic",
    verbose: bool = True,
) -> BenchmarkResult:
    """Run the full comparison; see module docstring for the contract."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    records: List[Dict[str, Any]] = []

    for planner_name in planners:
        for seed in seeds:
            runner = create_mission(
                cfg, planner_name=planner_name, backend_name=backend, seed_offset=seed
            )
            try:
                result = runner.run()
            finally:
                runner.backend.close()

            plume = runner.plume
            grid = EvalGrid(cfg.survey, plume.seabed_z, cfg.compliance.eval_altitude_m)
            truth = plume.ground_truth(grid.points, t=0.0)
            bed_out = float(plume.seabed_z(cfg.outfall.x, cfg.outfall.y))
            ambient_bottom = float(plume.ambient_salinity(bed_out))
            threshold = boundary_salinity_psu(cfg, plume)
            true_xy = plume.outfall_xy()

            gt_verdict = evaluate_compliance(
                truth, None, grid, true_xy, cfg.compliance, ambient_bottom
            )

            for frac in cfg.budget.checkpoints:
                budget_m = frac * cfg.budget.max_distance_m
                subset = result.samples_within_budget(budget_m)
                mapper = GPMapper(cfg.gp, plume.ambient_salinity, seed=cfg.seed + 31)
                mapper.add_samples(subset)
                mean, std = mapper.predict(grid.points)

                verdict = evaluate_compliance(
                    mean, std, grid, true_xy, cfg.compliance, ambient_bottom
                )
                metrics = compute_metrics(
                    mean, truth, grid, subset, threshold, plume=plume
                )
                screening = screen(verdict, cfg.compliance)
                s_outcome = screening_outcome(screening, gt_verdict.compliant)
                records.append({
                    "planner": planner_name,
                    "seed": int(seed),
                    "checkpoint_frac": float(frac),
                    "budget_m": float(budget_m),
                    "n_samples": metrics.n_samples,
                    "rmse_all": metrics.rmse_all,
                    "rmse_plume": metrics.rmse_plume,
                    "mae_all": metrics.mae_all,
                    "boundary_f1": metrics.boundary_f1,
                    "boundary_iou": metrics.boundary_iou,
                    "coverage_frac": metrics.coverage_frac,
                    "in_plume_frac": metrics.in_plume_frac,
                    "compliant": bool(verdict.compliant),
                    "gt_compliant": bool(gt_verdict.compliant),
                    "verdict_correct": bool(verdict.compliant == gt_verdict.compliant),
                    "max_exceedance_psu": float(verdict.max_exceedance_psu),
                    "prob_exceed_max": float(verdict.prob_exceed_max),
                    "max_std_outside_psu": float(verdict.max_std_outside_psu),
                    "screening_state": screening.state.value,
                    "screening_outcome": s_outcome,
                })
            if verbose:
                last = records[-1]
                print(f"[benchmark] {planner_name} seed={seed}: "
                      f"{len(result.samples)} samples, "
                      f"rmse_plume={last['rmse_plume']:.3f} PSU, "
                      f"F1={last['boundary_f1']:.2f}, "
                      f"verdict {'OK' if last['verdict_correct'] else 'WRONG'}")

    summary = _summarize(records, planners, cfg.budget.checkpoints)
    _save_csv(records, out / "benchmark_records.csv")
    with open(out / "benchmark_summary.json", "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    return BenchmarkResult(records=records, summary=summary)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _summarize(
    records: List[Dict[str, Any]],
    planners: Sequence[str],
    checkpoints: Sequence[float],
) -> Dict[str, Any]:
    """planner -> checkpoint -> {metric: {mean, std}} + verdict_accuracy."""
    summary: Dict[str, Any] = {}
    for planner in planners:
        summary[planner] = {}
        for frac in checkpoints:
            rows = [r for r in records
                    if r["planner"] == planner and r["checkpoint_frac"] == float(frac)]
            if not rows:
                continue
            entry: Dict[str, Any] = {}
            for metric in SUMMARY_METRICS:
                values = [float(r[metric]) for r in rows
                          if not math.isnan(float(r[metric]))]
                if values:
                    entry[metric] = {
                        "mean": float(np.mean(values)),
                        "std": float(np.std(values)),
                    }
            entry["verdict_accuracy"] = float(
                np.mean([1.0 if r["verdict_correct"] else 0.0 for r in rows])
            )
            # Three-state screening: conclusive-and-correct / inconclusive /
            # conclusive-and-wrong fractions (REVIEW is honest, not an error)
            n = len(rows)
            for outcome_name in ("correct", "inconclusive", "wrong"):
                entry[f"screening_{outcome_name}"] = float(
                    sum(1 for r in rows if r.get("screening_outcome") == outcome_name) / n
                )
            summary[planner][f"{float(frac):g}"] = entry
    return summary


def _save_csv(records: List[Dict[str, Any]], path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=RECORD_KEYS)
        writer.writeheader()
        for rec in records:
            writer.writerow(rec)

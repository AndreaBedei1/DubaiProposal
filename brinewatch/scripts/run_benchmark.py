"""Run the equal-budget lawnmower-vs-adaptive benchmark.

Usage (from the repo root, inside the conda env):

    python scripts/run_benchmark.py --config configs/benchmark.yaml --seeds 5
    python scripts/run_benchmark.py --budget 1200 --seeds 3
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from brinewatch.evaluation.benchmark import run_benchmark
from brinewatch.utils.config import load_config, save_config
from brinewatch.utils.logging_utils import make_run_dir
from brinewatch.visualization.plots import plot_learning_curves


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", type=str, default=None, help="YAML mission config")
    ap.add_argument("--seeds", type=int, default=5, help="number of seeds per planner")
    ap.add_argument("--backend", type=str, default=None, choices=[None, "kinematic", "holoocean"])
    ap.add_argument("--budget", type=float, default=None, help="override budget in metres")
    ap.add_argument("--out", type=str, default=str(REPO_ROOT / "outputs"))
    args = ap.parse_args()

    overrides = {}
    if args.budget is not None:
        overrides["budget"] = {"max_distance_m": float(args.budget)}
    cfg = load_config(args.config, overrides=overrides or None)
    backend = args.backend or cfg.backend.name

    run_dir = make_run_dir(args.out, cfg.name)
    print(f"[benchmark] run dir: {run_dir}")
    save_config(cfg, run_dir / "config_used.yaml")

    result = run_benchmark(
        cfg, run_dir, seeds=tuple(range(args.seeds)), backend=backend, verbose=True
    )
    curves = plot_learning_curves(result.records, run_dir / "learning_curves.png")

    # ------------------------------------------------------------------ #
    # Final comparison table at the last checkpoint
    # ------------------------------------------------------------------ #
    last = f"{max(cfg.budget.checkpoints):g}"
    print("\n=== Final comparison (budget fraction "
          f"{last}, {args.seeds} seeds, mean +/- std) ===")
    header = f"{'planner':<12} {'rmse_plume':>16} {'boundary_f1':>16} {'coverage':>16} {'verdict acc':>12}"
    print(header)
    print("-" * len(header))
    for planner, by_frac in result.summary.items():
        entry = by_frac.get(last, {})

        def cell(metric: str) -> str:
            stats = entry.get(metric)
            if not stats:
                return "n/a"
            return f"{stats['mean']:.3f} +/- {stats['std']:.3f}"

        print(f"{planner:<12} {cell('rmse_plume'):>16} {cell('boundary_f1'):>16} "
              f"{cell('coverage_frac'):>16} {entry.get('verdict_accuracy', float('nan')):>12.2f}")

    print(f"\n[benchmark] records: {run_dir / 'benchmark_records.csv'}")
    print(f"[benchmark] summary: {run_dir / 'benchmark_summary.json'}")
    print(f"[benchmark] curves:  {curves}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

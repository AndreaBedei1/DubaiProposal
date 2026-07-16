"""Integration test for the equal-budget benchmark harness."""
from __future__ import annotations

import csv
import json

from brinewatch.evaluation.benchmark import RECORD_KEYS, run_benchmark
from brinewatch.utils.config import load_config

FAST_OVERRIDES = {
    "budget": {"max_distance_m": 500.0, "checkpoints": [0.5, 1.0]},
    "survey": {"grid_resolution_m": 6.0},
    "gp": {"max_train_points": 300},
}


def test_benchmark_contract(tmp_path):
    cfg = load_config(None, overrides=FAST_OVERRIDES)
    result = run_benchmark(cfg, tmp_path, seeds=(0, 1), backend="kinematic",
                           verbose=False)

    # 2 planners x 2 seeds x 2 checkpoints
    assert len(result.records) == 8
    for rec in result.records:
        for key in RECORD_KEYS:
            assert key in rec, f"record missing '{key}'"
        assert isinstance(rec["compliant"], bool)
        assert isinstance(rec["gt_compliant"], bool)
        assert isinstance(rec["verdict_correct"], bool)
        assert rec["n_samples"] > 0

    # Files written and parseable
    csv_path = tmp_path / "benchmark_records.csv"
    json_path = tmp_path / "benchmark_summary.json"
    assert csv_path.exists() and json_path.exists()
    with open(csv_path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 8
    summary = json.loads(json_path.read_text(encoding="utf-8"))
    assert set(summary.keys()) == {"lawnmower", "adaptive"}
    for planner in summary.values():
        for entry in planner.values():
            assert "verdict_accuracy" in entry
            assert 0.0 <= entry["verdict_accuracy"] <= 1.0

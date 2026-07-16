"""Mission logging: JSONL event log, CSV samples, and artifact directory."""
from __future__ import annotations

import csv
import datetime as _dt
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np

from .types import CTDSample, MissionResult


def make_run_dir(base: Union[str, Path], run_name: str) -> Path:
    """Create outputs/<run_name>_<timestamp>/ and return it."""
    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = Path(base) / f"{run_name}_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


class MissionLogger:
    """Append-only JSONL event log plus artifact writers for one mission run."""

    def __init__(self, run_dir: Union[str, Path]):
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self._events_path = self.run_dir / "mission_log.jsonl"
        self._fh = open(self._events_path, "a", encoding="utf-8")

    def event(self, kind: str, **payload: Any) -> None:
        record = {"kind": kind, **_jsonable(payload)}
        self._fh.write(json.dumps(record) + "\n")
        self._fh.flush()

    def close(self) -> None:
        if not self._fh.closed:
            self._fh.close()

    def __enter__(self) -> "MissionLogger":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


def _jsonable(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.floating, np.integer)):
        return obj.item()
    return obj


def save_samples_csv(samples: List[CTDSample], budget_at_sample: List[float], path: Union[str, Path]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["t", "x", "y", "z", "salinity_psu", "temperature_c", "depth_m", "budget_used_m"])
        for s, b in zip(samples, budget_at_sample):
            writer.writerow([f"{s.t:.2f}", f"{s.x:.3f}", f"{s.y:.3f}", f"{s.z:.3f}",
                             f"{s.salinity_psu:.4f}", f"{s.temperature_c:.4f}",
                             f"{s.depth_m:.3f}", f"{b:.1f}"])


def save_result_summary(result: MissionResult, path: Union[str, Path],
                        extra: Optional[Dict[str, Any]] = None) -> None:
    summary = {
        "planner": result.planner_name,
        "n_samples": len(result.samples),
        "budget_used_m": result.budget.used_m if result.budget else None,
        "budget_max_m": result.budget.max_distance_m if result.budget else None,
        "outfall_estimate": result.outfall_estimate,
        "n_detections": len(result.detections),
        "phase_history": result.phase_history,
        "wall_time_s": round(result.wall_time_s, 2),
        "notes": result.notes,
    }
    if extra:
        summary.update(_jsonable(extra))
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)

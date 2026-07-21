"""Integration test: collision-safe navigation in a full kinematic mission.

Runs the same short mission with and without a HazardField and checks that the
safe-nav version keeps the vehicle out of the localized structure envelope.
Engine-free (kinematic backend), deterministic.
"""
import dataclasses
from pathlib import Path

import numpy as np
import pytest

from brinewatch.mission.runner import create_mission
from brinewatch.planning.safe_nav import HazardField, SafeNavConfig
from brinewatch.simulation.outfall_scene import OutfallSceneConfig
from brinewatch.utils.config import load_config

CFG_PATH = Path(__file__).resolve().parents[1] / "configs" / "mission_default.yaml"


def _short_cfg():
    cfg = load_config(str(CFG_PATH))
    # small, fast mission that surveys right over the outfall
    return dataclasses.replace(
        cfg,
        budget=dataclasses.replace(cfg.budget, max_distance_m=280.0),
        survey=dataclasses.replace(cfg.survey, x_min=-55.0, x_max=-5.0,
                                   y_min=-25.0, y_max=25.0, altitude_m=2.0),
        seed=7,
    )


def _hazard_field(cfg):
    from brinewatch.plume.model import BrinePlume
    plume = BrinePlume(cfg.environment, cfg.outfall, cfg.plume)
    seabed = lambda x, y: float(plume.seabed_z(x, y))  # noqa: E731
    return HazardField.from_outfall(
        (cfg.outfall.x, cfg.outfall.y), cfg.outfall.axis_deg,
        OutfallSceneConfig(), seabed,
        SafeNavConfig(clearance_m=2.0, min_altitude_m=1.0))


def _min_structure_clearance(result, field):
    return min(field.structure_clearance(np.array([x, y, z]))
               for _, x, y, z in result.trajectory)


def test_safe_nav_keeps_vehicle_clear_of_structure():
    cfg = _short_cfg()
    field = _hazard_field(cfg)
    est = (cfg.outfall.x, cfg.outfall.y)

    # WITHOUT safe navigation
    runner0 = create_mission(cfg, backend_name="kinematic", estimate_override=est)
    r0 = runner0.run()

    # WITH safe navigation (same everything else)
    runner1 = create_mission(cfg, backend_name="kinematic", estimate_override=est,
                             hazard_field=field)
    r1 = runner1.run()

    assert len(r1.samples) > 0 and r1.budget.used_m > 0
    clear0 = _min_structure_clearance(r0, field)
    clear1 = _min_structure_clearance(r1, field)

    # safe nav never lets the vehicle enter the structure solid ...
    assert clear1 >= 0.0, f"entered structure envelope (min clearance {clear1:.2f} m)"
    # ... and keeps meaningfully more clearance than the naive run
    assert clear1 > clear0
    # the min believed clearance the runner tracked matches an independent recompute
    assert runner1._min_structure_clearance_m == pytest.approx(clear1, abs=1e-6)


def test_safe_nav_reports_detours_and_metric():
    cfg = _short_cfg()
    field = _hazard_field(cfg)
    runner = create_mission(cfg, backend_name="kinematic",
                            estimate_override=(cfg.outfall.x, cfg.outfall.y),
                            hazard_field=field)
    r = runner.run()
    assert runner._detours >= 1                     # some legs needed a detour
    assert any("collision-safe nav" in n for n in r.notes)

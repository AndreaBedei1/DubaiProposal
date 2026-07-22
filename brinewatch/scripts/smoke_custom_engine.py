"""Smoke test for the custom-engine integration (attach mode).

Preconditions: the fork engine is already running (scripts/launch_custom_engine.py
in another process) with the target level loaded.

Checks, in order, each printed as PASS/FAIL:
 1. fork client import via HOLOOCEAN_CUSTOM_ENGINE_PATH
 2. attach to the named isolated engine session + agent spawn
 3. tick + LocationSensor readout
 4. SpawnAsset a cylinder (static mesh) + tick
 5. sonar frame BEFORE vs AFTER spawn differs near the asset (octree rebuild)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from brinewatch.simulation.custom_engine import (  # noqa: E402
    activate_fork_client,
    attach_custom_environment,
    clear_spawned,
    make_asset_spawner,
    resolve_custom_engine,
)


def main() -> int:
    engine = resolve_custom_engine()
    holoocean = activate_fork_client(engine)
    print(f"PASS 1: fork client {holoocean.__version__ if hasattr(holoocean, '__version__') else '?'} "
          f"from {Path(holoocean.__file__).parent}")

    scenario = {
        "name": "custom_smoke",
        "world": engine.level,
        "package_name": "Ocean",
        "main_agent": "rov",
        "ticks_per_sec": 30,
        "frames_per_sec": False,   # REQUIRED in attach mode: make() blocks on
                                   # input() when the key is missing
        "agents": [{
            "agent_name": "rov",
            "agent_type": "BlueROV2",
            "sensors": [
                {"sensor_type": "LocationSensor", "socket": "IMUSocket"},
                {"sensor_type": "ImagingSonar", "socket": "SonarSocket",
                 "configuration": {
                     "RangeBins": 256, "AzimuthBins": 128,
                     "RangeMin": 1.0, "RangeMax": 30.0,
                     "InitOctreeRange": 40.0,
                     "Elevation": 20.0, "Azimuth": 120.0,
                     "TicksPerCapture": 30,
                     "ViewOctree": -1,
                 }},
            ],
            "control_scheme": 1,
            "location": [0.0, 0.0, -30.0],
            "rotation": [0.0, 0.0, 0.0],
        }],
    }

    env = attach_custom_environment(holoocean, scenario,
                                    show_viewport=True, verbose=False)
    print("PASS 2: attached to running engine")

    env.reset()
    cmd = np.array([0.0, 0.0, -30.0, 0.0, 0.0, 0.0], dtype=np.float64)

    def tick_for_sonar(max_ticks=240):
        last = None
        for _ in range(max_ticks):
            env.act("rov", cmd)
            state = env.tick()
            if "ImagingSonar" in state:
                last = np.asarray(state["ImagingSonar"], dtype=float).copy()
        return last

    state = None
    for _ in range(30):
        env.act("rov", cmd)
        state = env.tick()
    loc = np.asarray(state["LocationSensor"], dtype=float)
    print(f"PASS 3: ticking; agent at {np.round(loc, 2).tolist()}")

    before = tick_for_sonar()
    if before is None:
        print("FAIL 5: no sonar frame received (before-phase)")
        return 1

    spawn = make_asset_spawner(env, holoocean, label_prefix="smoke")
    # a fat vertical cylinder 8 m in front of the vehicle, spanning sonar beams
    spawn("cylinder", location=[float(loc[0]) + 8.0, float(loc[1]),
                                float(loc[2]) - 2.0],
          rotation=[0.0, 0.0, 0.0], scale=[1.2, 1.2, 6.0])
    env.tick()
    print("PASS 4: SpawnAsset command sent")
    time.sleep(0.5)

    after = tick_for_sonar()
    if after is None:
        print("FAIL 5: no sonar frame received (after-phase)")
        return 1

    diff = float(np.abs(after - before).mean())
    changed = not np.array_equal(after, before)
    print(f"{'PASS' if changed else 'FAIL'} 5: sonar frames "
          f"{'differ' if changed else 'are bit-identical'} "
          f"(mean |after-before| = {diff:.6f})")

    clear_spawned(env, holoocean)
    env.tick()
    print("cleanup: ClearSpawned sent")
    return 0 if changed else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Sanity-check the local HoloOcean installation for BrineWatch.

Prints version, installed packages/worlds, confirms the BlueROV2 agent and the
sensors BrineWatch uses. Run inside the conda env with HoloOcean installed:

    python scripts/inspect_holoocean.py [--launch]

``--launch`` also boots SimpleUnderwater for a 100-tick smoke run (requires a
GPU; takes ~30 s).
"""
from __future__ import annotations

import argparse
import sys


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--launch", action="store_true", help="also boot a short smoke run")
    args = ap.parse_args()

    try:
        import holoocean
    except ImportError:
        print("HoloOcean is NOT importable in this environment.")
        print("BrineWatch still works with the kinematic backend.")
        return 1

    print(f"holoocean version: {holoocean.__version__}")
    packages = holoocean.installed_packages()
    print(f"installed packages: {packages}")
    if "Ocean" not in packages:
        print("Package 'Ocean' missing -> run: python -c \"import holoocean; holoocean.install('Ocean')\"")
        return 1

    import holoocean.agents as ag
    assert hasattr(ag, "BlueROV2"), "BlueROV2 agent not found (need HoloOcean >= 2.x)"
    print("BlueROV2 agent: OK")

    from holoocean import sensors as sn
    needed = ["PoseSensor", "LocationSensor", "VelocitySensor", "DepthSensor",
              "DVLSensor", "RangeFinderSensor"]
    missing = [s for s in needed if not hasattr(sn, s)]
    print(f"required sensors: {'OK' if not missing else 'MISSING ' + str(missing)}")

    if args.launch:
        import numpy as np

        from brinewatch.simulation.holoocean_backend import build_scenario
        from brinewatch.utils.config import BackendConfig

        cfg = BackendConfig()
        scenario = build_scenario(cfg, (0.0, 0.0, -10.0))
        print("booting SimpleUnderwater ...")
        env = holoocean.make(scenario_cfg=scenario, show_viewport=True, verbose=False)
        cmd = np.array([0, 0, -10, 0, 0, 0], dtype=np.float64)
        state = None
        for _ in range(100):
            env.act("brine_rov", cmd)
            state = env.tick()
        print(f"smoke run OK — sensors seen: {sorted(state.keys())}")
    print("HoloOcean environment: READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

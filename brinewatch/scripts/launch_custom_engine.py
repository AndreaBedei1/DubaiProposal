"""Launch the custom HoloOcean fork engine via the UE editor in -game mode.

Engine path: auto-discovered (the in-project ``<repo>/engine`` directory), or
``HOLOOCEAN_CUSTOM_ENGINE_PATH`` if set (engine dir or a fork root).
Requires ``UNREAL_EDITOR_EXE`` -> UnrealEditor.exe (UE 5.3).

The engine stays in the foreground until killed; run it in a separate
process/console, then attach clients with holoocean.make(..., start_world=False).
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from brinewatch.simulation.custom_engine import (  # noqa: E402
    clear_octree_cache,
    discover_custom_engine,
    editor_launch_args,
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--level", default="ExampleLevel")
    ap.add_argument("--octree-min", type=float, default=0.05)
    ap.add_argument("--octree-max", type=float, default=5.0)
    ap.add_argument("--res", type=int, nargs=2, default=(1280, 720))
    ap.add_argument("--clear-cache", action="store_true",
                    help="delete the on-disk octree cache before boot so the "
                         "sonar octree is rebuilt from scratch (rules out a "
                         "stale cache leaking a previous session's geometry)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the command line and exit")
    args = ap.parse_args()

    engine = discover_custom_engine(level=args.level)
    if args.clear_cache:
        n = clear_octree_cache(engine)
        print(f"[launch_custom_engine] cleared {n} cached octree file(s) for "
              f"{engine.level}")
    print(f"[launch_custom_engine] engine: {engine.uproject}")
    cmd = editor_launch_args(engine, res=tuple(args.res),
                             octree_min_m=args.octree_min,
                             octree_max_m=args.octree_max)
    print("[launch_custom_engine] command:")
    print("  " + " ".join(f'"{c}"' if " " in c else c for c in cmd))
    if args.dry_run:
        return 0
    proc = subprocess.Popen(cmd, cwd=str(engine.root))
    print(f"[launch_custom_engine] engine PID {proc.pid} (level {engine.level})")
    proc.wait()
    return proc.returncode or 0


if __name__ == "__main__":
    raise SystemExit(main())

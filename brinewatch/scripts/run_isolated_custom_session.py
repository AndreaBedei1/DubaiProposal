"""Run one custom-HoloOcean client in a fully namespaced engine session.

The launcher creates a unique UUID suffix for every semaphore/shared-memory
object, and separate work/output/temp/DDC/octree/log directories. It records
the exact process inventory, starts the custom engine, waits for its private
loading semaphore, runs one client command, and terminates only the engine PID
it created. It never searches for, kills, or modifies another HoloOcean
process.

Examples:
    python scripts/run_isolated_custom_session.py
    python scripts/run_isolated_custom_session.py --client scripts/smoke_custom_engine.py
    python scripts/run_isolated_custom_session.py --client scripts/run_custom_holoocean_mission.py -- --budget 260
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from brinewatch.simulation.custom_engine import (  # noqa: E402
    clear_octree_cache,
    discover_custom_engine,
    editor_launch_args,
    prepare_isolated_runtime,
    validate_instance_id,
)


def _process_inventory() -> list[dict]:
    """Read-only snapshot used to prove that unrelated processes were untouched."""
    try:
        import psutil
    except ImportError:
        return []
    rows = []
    for proc in psutil.process_iter(["pid", "name", "cmdline", "create_time"]):
        try:
            name = proc.info.get("name") or ""
            cmd = " ".join(proc.info.get("cmdline") or [])
            if "holo" in name.lower() or "unreal" in name.lower() or "holoocean" in cmd.lower():
                rows.append({
                    "pid": proc.info["pid"],
                    "name": name,
                    "command": cmd,
                    "create_time": proc.info.get("create_time"),
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return rows


def _write_manifest(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--client", default=str(REPO / "scripts" / "run_custom_holoocean_mission.py"))
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--instance-id", default=None)
    ap.add_argument("--runtime-root", default=None)
    ap.add_argument("--level", default="ExampleLevel")
    ap.add_argument("--res", type=int, nargs=2, default=(1280, 720))
    ap.add_argument("--startup-timeout", type=float, default=180.0)
    ap.add_argument("--keep-engine", action="store_true",
                    help="leave this launcher-owned engine running after the client exits")
    ap.add_argument("client_args", nargs=argparse.REMAINDER)
    args = ap.parse_args()

    instance_id = validate_instance_id(
        args.instance_id or f"brinewatch-{uuid.uuid4().hex[:12]}")
    runtime = prepare_isolated_runtime(
        instance_id, Path(args.runtime_root) if args.runtime_root else None)
    engine = discover_custom_engine(level=args.level)
    clear_octree_cache(engine, runtime.octree_dir)

    engine_log = runtime.log_dir / "HolodeckCustom.log"
    stdio_log = runtime.log_dir / "engine_stdio.log"
    cmd = editor_launch_args(
        engine,
        res=tuple(args.res),
        instance_id=instance_id,
        octree_cache_root=runtime.octree_dir,
        absolute_log=engine_log,
    )
    client_args = list(args.client_args)
    if client_args and client_args[0] == "--":
        client_args = client_args[1:]
    client_cmd = [args.python, str(Path(args.client).resolve()), *client_args]

    child_env = os.environ.copy()
    child_env["BRINEWATCH_HOLOOCEAN_INSTANCE_ID"] = instance_id
    child_env["BRINEWATCH_RUNTIME_ROOT"] = str(runtime.root.parent)
    child_env["BRINEWATCH_SESSION_OUTPUT_DIR"] = str(runtime.output_dir)
    child_env["TEMP"] = str(runtime.temp_dir)
    child_env["TMP"] = str(runtime.temp_dir)
    child_env["UE-LocalDataCachePath"] = str(runtime.cache_dir / "local")
    child_env["UE-SharedDataCachePath"] = str(runtime.cache_dir / "shared")
    child_env["PYTHONUNBUFFERED"] = "1"

    manifest_path = runtime.root / "run_manifest.json"
    manifest = {
        "instance_id": instance_id,
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "runtime_root": str(runtime.root),
        "engine_command": cmd,
        "client_command": client_cmd,
        "processes_before": _process_inventory(),
        "engine_pid": None,
        "client_exit_code": None,
        "engine_owned_by_launcher": True,
        "other_processes_terminated": [],
    }
    _write_manifest(manifest_path, manifest)

    print(f"[isolated] instance {instance_id}")
    print(f"[isolated] runtime {runtime.root}")
    print(f"[isolated] existing HoloOcean/Unreal processes observed: "
          f"{len(manifest['processes_before'])}; none will be modified")

    loading = None
    if os.name == "nt":
        import win32event
        loading = win32event.CreateSemaphore(
            None, 0, 1, f"Global\\HOLODECK_LOADING_SEM{instance_id}")

    with stdio_log.open("w", encoding="utf-8", errors="replace") as log_handle:
        engine_proc = subprocess.Popen(
            cmd,
            cwd=str(runtime.work_dir),
            env=child_env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0),
        )
        manifest["engine_pid"] = engine_proc.pid
        _write_manifest(manifest_path, manifest)
        print(f"[isolated] launched owned engine PID {engine_proc.pid}")

        try:
            if loading is not None:
                import win32event
                response = win32event.WaitForSingleObject(
                    loading, int(args.startup_timeout * 1000))
                if response != win32event.WAIT_OBJECT_0:
                    raise TimeoutError("private HoloOcean loading semaphore timed out")
            else:
                deadline = time.time() + args.startup_timeout
                while time.time() < deadline:
                    if engine_proc.poll() is not None:
                        raise RuntimeError("custom engine exited during startup")
                    if engine_log.exists() and "started successfully" in engine_log.read_text(
                            encoding="utf-8", errors="ignore"):
                        break
                    time.sleep(0.5)
                else:
                    raise TimeoutError("custom engine startup log timed out")

            print("[isolated] private engine ready; starting client")
            client = subprocess.run(client_cmd, cwd=str(runtime.work_dir), env=child_env)
            manifest["client_exit_code"] = client.returncode
            return_code = client.returncode
        except Exception as exc:
            manifest["error"] = f"{type(exc).__name__}: {exc}"
            print(f"[isolated] ERROR: {manifest['error']}")
            return_code = 1
        finally:
            if not args.keep_engine and engine_proc.poll() is None:
                print(f"[isolated] stopping owned engine PID {engine_proc.pid}")
                engine_proc.terminate()
                try:
                    engine_proc.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    engine_proc.kill()
                    engine_proc.wait(timeout=10)
            manifest["engine_exit_code"] = engine_proc.poll()
            manifest["finished_utc"] = datetime.now(timezone.utc).isoformat()
            manifest["processes_after"] = _process_inventory()
            _write_manifest(manifest_path, manifest)
            print(f"[isolated] manifest {manifest_path}")

    return return_code


if __name__ == "__main__":
    raise SystemExit(main())

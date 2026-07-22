"""Integration with the custom HoloOcean engine fork (runtime octree rebuild).

The official HoloOcean 2.3.0 engine builds the acoustic octree once from the
level's static geometry: props spawned at runtime are camera-visible but
sonar-invisible (proven bit-identical A/B sonar frames, see
docs/application/pfh2026/SONAR_VALIDATION.md). The custom fork adds:

- ``SpawnAsset`` world command: spawns a *static-mesh actor* (Mobility=Static,
  BlockAll collision) from any UE mesh asset path, with a true
  ``[roll, pitch, yaw]`` rotation (C++ ``RPYToRotator``, NOT the direction-
  vector quirk of the ``SpawnProp`` blueprint), then calls
  ``Octree::MarkWorldGeometryDirty()``.
- ``ClearSpawned`` / ``RespawnFromConfig`` world commands (also mark dirty).
- ``HolodeckSonar::Tick`` consumes the dirty flag: clears the on-disk octree
  cache for the current map and rebuilds the octree, so the spawned structure
  becomes acoustically visible on the next sonar frame.

Deployment model (no packaged binary ships with the fork): the engine runs
from the UE 5.3 editor - either interactively (Play In Editor as standalone)
or headless-ish via ``UnrealEditor.exe <uproject> <Level> -game``. The fork's
Python client attaches through :func:`attach_custom_environment`, which passes
the same explicit per-run UUID to the engine, semaphores and shared memory.

Nothing here hard-codes user-specific paths: the fork checkout location comes
from the ``HOLOOCEAN_CUSTOM_ENGINE_PATH`` environment variable and every
failure mode raises :class:`CustomEngineError` with an actionable message.
"""
from __future__ import annotations

import math
import os
import re
import sys
import json
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Sequence

ENV_VAR = "HOLOOCEAN_CUSTOM_ENGINE_PATH"
CLIENT_ENV_VAR = "HOLOOCEAN_CUSTOM_CLIENT_PATH"
INSTANCE_ENV_VAR = "BRINEWATCH_HOLOOCEAN_INSTANCE_ID"
RUNTIME_ENV_VAR = "BRINEWATCH_RUNTIME_ROOT"
DEFAULT_LEVEL = "ExampleLevel"

#: UE basic-shape meshes used to mirror the official ``spawn_prop`` primitives.
#: Available in editor/-game runs without cooking.
PROP_MESHES = {
    "cylinder": "/Engine/BasicShapes/Cylinder.Cylinder",
    "box": "/Engine/BasicShapes/Cube.Cube",
    "sphere": "/Engine/BasicShapes/Sphere.Sphere",
    "cone": "/Engine/BasicShapes/Cone.Cone",
}

# Sign conventions for the client-frame [roll, pitch, yaw] sent to SpawnAsset.
# To be confirmed by a calibration render against the custom engine (same
# harness as the official-engine one); flip if the render disagrees.
PITCH_SIGN = 1.0
YAW_SIGN = 1.0


class CustomEngineError(RuntimeError):
    """The custom engine is unavailable or misconfigured. Never fall back
    silently: acoustic claims about the custom engine must not be produced
    by the official engine."""


@dataclass(frozen=True)
class CustomEngine:
    root: Path                     # engine project root (holds Holodeck.uproject)
    uproject: Path                 # <root>/Holodeck.uproject
    client_src: Optional[Path]     # fork client's src dir, or None -> official client
    octrees_dir: Path              # <root>/Octrees (on-disk acoustic octree cache)
    level: str = DEFAULT_LEVEL


@dataclass(frozen=True)
class IsolatedRuntime:
    """Filesystem and IPC namespace reserved for one BrineWatch engine run."""

    instance_id: str
    root: Path
    work_dir: Path
    output_dir: Path
    temp_dir: Path
    cache_dir: Path
    octree_dir: Path
    log_dir: Path


def validate_instance_id(value: str) -> str:
    """Validate a HoloOcean UUID suffix before it reaches named IPC objects."""
    value = str(value).strip()
    if not value or not re.fullmatch(r"[A-Za-z0-9_-]{6,64}", value):
        raise CustomEngineError(
            "invalid BrineWatch HoloOcean instance id. Use 6-64 ASCII letters, "
            "digits, '_' or '-' (for example 'brinewatch-a1b2c3d4')."
        )
    return value


def isolated_instance_id(required: bool = True) -> str:
    """Return the IPC namespace shared by the custom engine and its client."""
    raw = os.environ.get(INSTANCE_ENV_VAR, "").strip()
    if raw:
        return validate_instance_id(raw)
    if required:
        raise CustomEngineError(
            f"{INSTANCE_ENV_VAR} is not set. Launch custom-engine work through "
            "scripts/run_isolated_custom_session.py (recommended), or export a "
            "unique instance id in both the engine and client terminals."
        )
    return ""


def prepare_isolated_runtime(instance_id: str,
                             root: Optional[Path] = None) -> IsolatedRuntime:
    """Create per-instance work/output/temp/cache/octree/log directories."""
    instance_id = validate_instance_id(instance_id)
    configured_root = os.environ.get(RUNTIME_ENV_VAR, "").strip()
    base = Path(root) if root is not None else (
        Path(configured_root) if configured_root else repo_root() / ".runtime" / "holoocean")
    runtime_root = base.expanduser().resolve() / instance_id
    dirs = {
        "work_dir": runtime_root / "work",
        "output_dir": runtime_root / "outputs",
        "temp_dir": runtime_root / "temp",
        "cache_dir": runtime_root / "cache",
        "octree_dir": runtime_root / "octrees",
        "log_dir": runtime_root / "logs",
    }
    for directory in dirs.values():
        directory.mkdir(parents=True, exist_ok=True)
    runtime = IsolatedRuntime(instance_id=instance_id, root=runtime_root, **dirs)
    manifest = {
        "instance_id": instance_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "ipc": {
            "loading_semaphore": f"Global\\HOLODECK_LOADING_SEM{instance_id}",
            "server_semaphore": f"Global\\HOLODECK_SEMAPHORE_SERVER{instance_id}",
            "client_semaphore": f"Global\\HOLODECK_SEMAPHORE_CLIENT{instance_id}",
            "shared_memory_prefix": f"/HOLODECK_MEM{instance_id}_",
        },
        "directories": {key: str(value) for key, value in dirs.items()},
    }
    (runtime_root / "session_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    return runtime


def repo_root() -> Path:
    """The BrineWatch repository root (holds brinewatch/ and, when present, engine/)."""
    # .../brinewatch/brinewatch/simulation/custom_engine.py -> parents[3] = repo root
    return Path(__file__).resolve().parents[3]


def _uproject_from(candidate: Path) -> Optional[Path]:
    """Accept either an engine dir (holds Holodeck.uproject) or a fork root
    (holds engine/Holodeck.uproject); return the uproject path or None."""
    candidate = Path(candidate).expanduser()
    for up in (candidate / "Holodeck.uproject",
               candidate / "engine" / "Holodeck.uproject"):
        if up.is_file():
            return up
    return None


def _find_engine_uproject() -> Path:
    """Discover the custom-engine uproject. Order:

    1. ``HOLOOCEAN_CUSTOM_ENGINE_PATH`` (engine dir OR fork root), if set;
    2. the in-project ``<repo>/engine`` directory (auto-discovery, preferred);
    3. a ``engine/`` sibling of the repo, if any.
    """
    tried = []
    raw = os.environ.get(ENV_VAR, "").strip()
    if raw:
        up = _uproject_from(Path(raw))
        if up:
            return up
        tried.append(f"{ENV_VAR}={raw}")
    for cand in (repo_root() / "engine", repo_root().parent / "engine"):
        up = _uproject_from(cand)
        if up:
            return up
        tried.append(str(cand))
    raise CustomEngineError(
        "custom HoloOcean engine not found. Place the fork engine at "
        f"<repo>/engine/Holodeck.uproject, or set {ENV_VAR} to the engine "
        "directory (or a fork root containing engine/). Tried: "
        + "; ".join(tried)
    )


def _find_fork_client(engine_root: Path) -> Optional[Path]:
    """Discover the fork's Python client src dir, or None (use the official
    client for attach). Order:

    1. ``HOLOOCEAN_CUSTOM_CLIENT_PATH``, if set;
    2. a ``client/src`` sibling of the engine root (classic fork layout);
    3. ``client/src`` under the repo, if the fork client was vendored there.
    """
    raw = os.environ.get(CLIENT_ENV_VAR, "").strip()
    candidates = []
    if raw:
        p = Path(raw).expanduser()
        candidates += [p, p / "src", p / "client" / "src"]
    candidates += [
        engine_root.parent / "client" / "src",   # <fork>/client/src (engine at <fork>/engine)
        repo_root() / "client" / "src",           # vendored into the repo
    ]
    for c in candidates:
        if (c / "holoocean" / "__init__.py").is_file():
            return c
    return None


def discover_custom_engine(level: str = DEFAULT_LEVEL) -> CustomEngine:
    """Auto-discover the custom engine (and fork client if available).

    The engine is required and located via :func:`_find_engine_uproject`; the
    fork client is optional (falls back to the installed official client for
    attach mode — see :func:`activate_fork_client`)."""
    uproject = _find_engine_uproject()
    root = uproject.parent
    return CustomEngine(root=root, uproject=uproject,
                        client_src=_find_fork_client(root),
                        octrees_dir=root / "Octrees", level=level)


# Backwards-compatible alias used by existing scripts.
def resolve_custom_engine(level: str = DEFAULT_LEVEL) -> CustomEngine:
    return discover_custom_engine(level=level)


def activate_fork_client(engine: CustomEngine):
    """Import the HoloOcean client used to attach to the fork engine.

    If ``engine.client_src`` is set, that fork client takes import precedence
    (prepended to ``sys.path``); otherwise the installed official client is
    imported as a fallback for attach mode (``SpawnAsset``/``ClearSpawned``
    are engine-side world commands, sent through the generic ``Command`` API).

    Must run before anything else imports ``holoocean``: Python caches modules,
    so a client cannot be swapped once imported.
    """
    existing = sys.modules.get("holoocean")
    if existing is not None:
        loaded_from = Path(getattr(existing, "__file__", "?")).resolve()
        if engine.client_src is not None and engine.client_src not in loaded_from.parents:
            raise CustomEngineError(
                f"holoocean is already imported from {loaded_from}, not the "
                f"fork client at {engine.client_src}. Run custom-engine "
                "scripts in a fresh process."
            )
        return existing
    if engine.client_src is not None:
        sys.path.insert(0, str(engine.client_src))
    import holoocean  # noqa: PLC0415

    loaded_from = Path(holoocean.__file__).resolve()
    if engine.client_src is not None and engine.client_src not in loaded_from.parents:
        raise CustomEngineError(
            f"import holoocean resolved to {loaded_from}, not the fork client "
            f"under {engine.client_src}. Check the environment."
        )
    return holoocean


def clear_octree_cache(engine: CustomEngine,
                       cache_root: Optional[Path] = None) -> int:
    """Delete on-disk cached octrees for the current level so the next boot
    rebuilds from scratch (guards against stale caches leaking a previous
    session's spawned geometry into a fresh run). Returns the number of files
    removed. Safe to call when the engine is not running."""
    removed = 0
    cache = Path(cache_root or engine.octrees_dir) / engine.level
    if cache.is_dir():
        for f in cache.glob("*"):
            try:
                if f.is_file():
                    f.unlink()
                    removed += 1
            except OSError:
                pass
    return removed


def editor_launch_args(
    engine: CustomEngine,
    editor_exe: Optional[str] = None,
    res: tuple = (1280, 720),
    octree_min_m: float = 0.05,
    octree_max_m: float = 5.0,
    env_min: tuple = (-100.0, -100.0, -100.0),
    env_max: tuple = (100.0, 100.0, 10.0),
    frames_per_sec: Optional[int] = None,
    instance_id: Optional[str] = None,
    octree_cache_root: Optional[Path] = None,
    absolute_log: Optional[Path] = None,
    extra: Sequence[str] = (),
) -> List[str]:
    """Command line to run the fork engine via the UE editor in -game mode.

    The client attaches afterwards with :func:`attach_custom_environment` and
    the exact ``instance_id`` used here. This keeps named IPC separate from
    other HoloOcean sessions.
    """
    exe = editor_exe or os.environ.get("UNREAL_EDITOR_EXE", "").strip()
    if not exe and os.name == "nt":
        program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        candidates = sorted(
            program_files.glob(
                "Epic Games/UE_5.*/Engine/Binaries/Win64/UnrealEditor.exe"),
            reverse=True,
        )
        if candidates:
            exe = str(candidates[0])
    if not exe:
        raise CustomEngineError(
            "no Unreal editor executable configured: pass editor_exe or set "
            "UNREAL_EDITOR_EXE (e.g. C:\\Program Files\\Epic Games\\UE_5.3\\"
            "Engine\\Binaries\\Win64\\UnrealEditor.exe)."
        )
    if not Path(exe).is_file():
        raise CustomEngineError(f"Unreal editor executable not found: {exe}")
    args = [
        exe,
        str(engine.uproject),
        engine.level,
        "-game",
        "-windowed",
        f"-ResX={res[0]}",
        f"-ResY={res[1]}",
        "-ForceRes",
        # Octree::initOctree parses these in CLIENT units (meters); without
        # EnvMin/EnvMax the acoustic octree only covers +-10 m around origin.
        f"-OctreeMin={octree_min_m}",
        f"-OctreeMax={octree_max_m}",
        f"-EnvMinX={env_min[0]}", f"-EnvMinY={env_min[1]}", f"-EnvMinZ={env_min[2]}",
        f"-EnvMaxX={env_max[0]}", f"-EnvMaxY={env_max[1]}", f"-EnvMaxZ={env_max[2]}",
    ]
    if instance_id:
        args.append(f"--HolodeckUUID={validate_instance_id(instance_id)}")
    if octree_cache_root is not None:
        args.append(f"-OctreeCacheRoot={Path(octree_cache_root).resolve()}")
    if absolute_log is not None:
        args.append(f"-abslog={Path(absolute_log).resolve()}")
    else:
        args.append("-LOG=HolodeckCustom.log")
    if frames_per_sec:
        args.append(f"-FramesPerSec={int(frames_per_sec)}")
    args.extend(extra)
    return args


def attach_custom_environment(holoocean_mod, scenario: dict,
                              show_viewport: bool = True,
                              verbose: bool = False,
                              instance_id: Optional[str] = None):
    """Attach to a custom engine with an explicit isolated IPC namespace.

    HoloOcean 2.3.0's ``make(..., start_world=False)`` does not expose its
    internal ``uuid`` argument and silently uses the global empty suffix.
    Constructing ``HoloOceanEnvironment`` directly preserves the scenario
    behavior while namespacing loading semaphores, lock-step semaphores, and
    every shared-memory block.
    """
    iid = validate_instance_id(instance_id or isolated_instance_id())
    env_cls = holoocean_mod.environments.HoloOceanEnvironment
    ticks = scenario.get("ticks_per_sec", 30)
    frames = scenario.get("frames_per_sec", 30)
    return env_cls(
        scenario=scenario,
        start_world=False,
        uuid=iid,
        show_viewport=show_viewport,
        verbose=verbose,
        ticks_per_sec=ticks,
        frames_per_sec=frames,
        set_tps=True,
        set_fps=True if frames is not False else None,
    )


# --------------------------------------------------------------------------- #
# Spawning
# --------------------------------------------------------------------------- #
def _spawn_asset_command(holoocean_mod, mesh_asset_path: str,
                         location: Sequence[float],
                         rotation_rpy: Sequence[float],
                         scale: Sequence[float], label: str = "",
                         units: str = "m"):
    """Build a SpawnAsset command object using the fork client's Command base."""
    Command = holoocean_mod.command.Command

    cmd = Command()
    cmd.set_command_type("SpawnAsset")
    cmd.add_number_parameters([float(v) for v in location])
    cmd.add_number_parameters([float(v) for v in rotation_rpy])
    cmd.add_number_parameters([float(v) for v in scale])
    cmd.add_string_parameters(mesh_asset_path)
    cmd.add_string_parameters(label)
    cmd.add_string_parameters(units)
    return cmd


def direction_to_rpy(rotation: Sequence[float]) -> List[float]:
    """Convert an outfall-scene rotation triple to SpawnAsset [roll,pitch,yaw].

    ``OutfallSceneBuilder`` encodes orientations for the official
    ``spawn_prop`` quirk: the triple is a *direction vector* ``d`` produced by
    :func:`~brinewatch.simulation.outfall_scene.prop_rotation_for_axis`,
    ``d = (-cos(psi) cos(tau), -sin(psi) cos(tau), sin(tau))`` for a long axis
    at tilt-from-vertical ``tau`` and heading ``psi``. SpawnAsset instead
    takes a true rotator, for which the long (local +Z) axis lands on
    ``Rz(yaw)·Ry(pitch)·z = (sin p cos w, sin p sin w, cos p)``:
    pitch = tau, yaw = psi.
    """
    a, b, c = (float(v) for v in rotation[:3])
    n = math.sqrt(a * a + b * b + c * c)
    if n < 1e-9:
        return [0.0, 0.0, 0.0]  # vertical / identity
    tau = math.degrees(math.asin(max(-1.0, min(1.0, c / n))))
    psi = math.degrees(math.atan2(-b, -a))
    return [0.0, PITCH_SIGN * tau, YAW_SIGN * psi]


def make_asset_spawner(env, holoocean_mod, label_prefix: str = "brinewatch") -> Callable:
    """A drop-in replacement for ``env.spawn_prop`` backed by SpawnAsset.

    Signature-compatible with the calls made by ``OutfallSceneBuilder._spawn``:
    ``fn(prop_type, location=..., rotation=..., scale=..., sim_physics=...,
    material=...)``. Materials are not supported by SpawnAsset (meshes keep
    their default material) — irrelevant for acoustics, and the visual gallery
    stays on the official engine.
    """
    counter = {"n": 0}

    def spawn(prop_type: str, location=None, rotation=None, scale=None,
              sim_physics: bool = False, material: str = "") -> None:
        mesh = PROP_MESHES.get(str(prop_type).lower())
        if mesh is None:
            raise CustomEngineError(
                f"prop type '{prop_type}' has no mesh mapping for SpawnAsset"
            )
        counter["n"] += 1
        cmd = _spawn_asset_command(
            holoocean_mod,
            mesh,
            location or [0.0, 0.0, 0.0],
            direction_to_rpy(rotation or [0.0, 0.0, 0.0]),
            scale or [1.0, 1.0, 1.0],
            label=f"{label_prefix}_{counter['n']:03d}_{prop_type}",
            units="m",
        )
        env._enqueue_command(cmd)

    return spawn


def clear_spawned(env, holoocean_mod) -> None:
    """Remove every asset spawned via SpawnAsset (marks the octree dirty)."""
    Command = holoocean_mod.command.Command
    cmd = Command()
    cmd.set_command_type("ClearSpawned")
    env._enqueue_command(cmd)

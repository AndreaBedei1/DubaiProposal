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
from the UE 5.3 editor — either interactively (Play In Editor as standalone)
or headless-ish via ``UnrealEditor.exe <uproject> <Level> -game``. The fork's
Python client then attaches with ``holoocean.make(..., start_world=False)``
(shared memory with an empty UUID suffix).

Nothing here hard-codes user-specific paths: the fork checkout location comes
from the ``HOLOOCEAN_CUSTOM_ENGINE_PATH`` environment variable and every
failure mode raises :class:`CustomEngineError` with an actionable message.
"""
from __future__ import annotations

import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Sequence

ENV_VAR = "HOLOOCEAN_CUSTOM_ENGINE_PATH"
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
    root: Path
    client_src: Path
    uproject: Path
    level: str = DEFAULT_LEVEL


def resolve_custom_engine(level: str = DEFAULT_LEVEL) -> CustomEngine:
    """Locate and validate the fork checkout from ``HOLOOCEAN_CUSTOM_ENGINE_PATH``."""
    raw = os.environ.get(ENV_VAR, "").strip()
    if not raw:
        raise CustomEngineError(
            f"{ENV_VAR} is not set. Point it at the root of the custom "
            "HoloOcean fork (the directory containing client/ and engine/). "
            "The custom-engine experiments cannot run without it."
        )
    root = Path(raw).expanduser()
    client_src = root / "client" / "src"
    uproject = root / "engine" / "Holodeck.uproject"
    problems = []
    if not (client_src / "holoocean" / "__init__.py").is_file():
        problems.append(f"fork client not found at {client_src / 'holoocean'}")
    if not uproject.is_file():
        problems.append(f"engine project not found at {uproject}")
    if problems:
        raise CustomEngineError(
            f"{ENV_VAR}={root} does not look like the HoloOcean fork: "
            + "; ".join(problems)
        )
    return CustomEngine(root=root, client_src=client_src, uproject=uproject,
                        level=level)


def activate_fork_client(engine: CustomEngine):
    """Make ``import holoocean`` resolve to the fork's client and import it.

    Must run before anything else imports the official package: Python caches
    modules, so mixing the two in one process is not possible.
    """
    existing = sys.modules.get("holoocean")
    if existing is not None:
        loaded_from = Path(getattr(existing, "__file__", "?")).resolve()
        if engine.client_src not in loaded_from.parents:
            raise CustomEngineError(
                "the official holoocean package is already imported in this "
                f"process (from {loaded_from}); the fork client cannot be "
                "activated. Run custom-engine scripts in a fresh process."
            )
        return existing
    sys.path.insert(0, str(engine.client_src))
    import holoocean  # noqa: PLC0415

    loaded_from = Path(holoocean.__file__).resolve()
    if engine.client_src not in loaded_from.parents:
        raise CustomEngineError(
            f"import holoocean resolved to {loaded_from}, not the fork client "
            f"under {engine.client_src}. Check the environment."
        )
    return holoocean


def editor_launch_args(
    engine: CustomEngine,
    editor_exe: Optional[str] = None,
    res: tuple = (1280, 720),
    octree_min_m: float = 0.05,
    octree_max_m: float = 5.0,
    env_min: tuple = (-100.0, -100.0, -100.0),
    env_max: tuple = (100.0, 100.0, 10.0),
    frames_per_sec: Optional[int] = None,
    extra: Sequence[str] = (),
) -> List[str]:
    """Command line to run the fork engine via the UE editor in -game mode.

    The client attaches afterwards with ``make(..., start_world=False)``
    (shared memory, empty UUID — the -game engine uses the same default).
    """
    exe = editor_exe or os.environ.get("UNREAL_EDITOR_EXE", "").strip()
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
        "-LOG=HolodeckCustom.log",
        # Octree::initOctree parses these in CLIENT units (meters); without
        # EnvMin/EnvMax the acoustic octree only covers +-10 m around origin.
        f"-OctreeMin={octree_min_m}",
        f"-OctreeMax={octree_max_m}",
        f"-EnvMinX={env_min[0]}", f"-EnvMinY={env_min[1]}", f"-EnvMinZ={env_min[2]}",
        f"-EnvMaxX={env_max[0]}", f"-EnvMaxY={env_max[1]}", f"-EnvMaxZ={env_max[2]}",
    ]
    if frames_per_sec:
        args.append(f"-FramesPerSec={int(frames_per_sec)}")
    args.extend(extra)
    return args


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

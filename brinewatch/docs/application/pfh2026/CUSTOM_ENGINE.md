# Custom HoloOcean engine integration (runtime octree rebuild)

## Why

The official HoloOcean 2.3.0 engine builds its acoustic octree once per map
from static level geometry. Props spawned at runtime (`spawn_prop`) are
camera-visible but **sonar-invisible** — proven by bit-identical A/B sonar
frames in [SONAR_VALIDATION.md](SONAR_VALIDATION.md). That is why the earlier
demo localized stock world geometry co-located with the visual outfall.

The custom fork (ALAR HoloOcean fork: `client/`, `engine/` UE 5.3 project)
removes that limitation:

- `SpawnAsset` world command → spawns a **static-mesh actor**
  (Mobility=Static, collision BlockAll) from any UE mesh path, with a true
  `[roll, pitch, yaw]` rotator (C++ `RPYToRotator`), then calls
  `Octree::MarkWorldGeometryDirty()`.
- `ClearSpawned` / `RespawnFromConfig` do the same on removal/replace.
- `HolodeckSonar::Tick` consumes the dirty flag: clears the on-disk octree
  cache for the current map (`engine/Octrees/<Map>/...`) and rebuilds, so the
  spawned structure enters the acoustic world on the next sonar frame
  (engine log line: `HolodeckSonar: world geometry changed, rebuilding octree.`).

Source evidence: `engine/Source/Holodeck/ClientCommands/Private/SpawnAssetCommand.cpp`,
`Utils/Private/RuntimeRowSpawner.cpp` (lines marking the octree dirty),
`General/{Public,Private}/Octree.{h,cpp}` (`MarkWorldGeometryDirty`,
`ConsumeWorldGeometryDirty`, `ClearCacheForCurrentWorld`),
`HolodeckCore/Private/HolodeckSonar.cpp` (rebuild in `Tick`).

## Setup (no user-specific paths are committed)

```powershell
$env:HOLOOCEAN_CUSTOM_ENGINE_PATH = "<path to the fork checkout>"   # contains client/ and engine/
$env:UNREAL_EDITOR_EXE = "C:\Program Files\Epic Games\UE_5.3\Engine\Binaries\Win64\UnrealEditor.exe"
```

The fork ships **no packaged binary** (`engine/Binaries/Win64` holds editor
DLLs only), so the engine runs through the UE 5.3 editor:

```powershell
# terminal 1 — engine (stays up; first run compiles shaders)
python scripts\launch_custom_engine.py --level ExampleLevel

# terminal 2 — experiments attach to it
python scripts\smoke_custom_engine.py
```

`launch_custom_engine.py` passes the flags the engine parses at octree init:
`-OctreeMin/-OctreeMax` (meters) and `-EnvMinX..-EnvMaxZ` (meters, client
frame). **Without the Env bounds the octree covers only ±10 m around the
world origin** (`Octree::initOctree` defaults) and nothing outside is
acoustically visible.

**Operational constraints found empirically** (2026-07-16):

- The scenario dict MUST contain `ticks_per_sec` and `frames_per_sec`:
  the fork's `make()` otherwise blocks forever on a hidden `input()` prompt.
- **One engine session serves one client session.** After a client detaches,
  the shared-memory semaphore pair is left mid-protocol and the next client
  blocks at its first `acquire`. Restart the engine between client runs.

The Python side then attaches with the FORK client
(`holoocean.make(..., start_world=False)`, shared memory, empty UUID); the
BrineWatch backend does this automatically for `backend.name:
holoocean_custom` (`brinewatch/simulation/custom_engine.py` +
`holoocean_backend.py`). The fork client is activated by prepending
`<fork>/client/src` to `sys.path` — custom-engine scripts must run in a fresh
process (a loud `CustomEngineError` is raised if the official package is
already imported, and there is **no silent fallback** to the official engine).

## Geometry mapping

`OutfallSceneBuilder` is spawn-backend agnostic (`spawn_fn` injection):

| backend | spawn call | rotation semantics | materials |
|---|---|---|---|
| holoocean (official) | `env.spawn_prop` | direction vector (UE `Conv_VectorToRotator` quirk, see SCENE_ITERATION_LOG) | stock prop materials |
| holoocean_custom | `SpawnAsset` (fork) | true `[roll, pitch, yaw]` — converted from the same internal direction triple by `custom_engine.direction_to_rpy` | default mesh material (irrelevant for acoustics) |

Primitive meshes: `/Engine/BasicShapes/{Cylinder, Cube, Sphere, Cone}`
(available in editor `-game` runs without cooking), `units="m"`.

## Honest boundaries

- Visual gallery screenshots come from the OFFICIAL engine (stock materials,
  validated scene): the custom engine renders the same geometry with default
  materials and is used for ACOUSTIC experiments only.
- Any claim of the form "the generated outfall is visible to sonar" applies
  to the custom engine only and must cite the A/B/C experiment
  (`scripts/validate_custom_sonar.py`), never the official engine.
- The custom engine runs the fork's `ExampleLevel` (its only full underwater
  level), not the official Ocean worlds: cross-engine results are therefore
  compared on the same structure geometry, not the same seabed.

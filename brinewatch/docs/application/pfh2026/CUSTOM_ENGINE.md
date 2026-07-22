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

## Setup (self-contained; no user-specific paths are committed)

For competition-generation work, use the namespaced one-command launcher in
[ISOLATED_EXECUTION.md](ISOLATED_EXECUTION.md). It assigns a unique UUID to
all HoloOcean semaphores/shared-memory blocks and private work, temp, DDC,
octree-cache, output, and log directories. This allows BrineWatch to coexist
with another HoloOcean workflow without attaching to or stopping it.

The fork engine is placed at `<repo>/engine` (the Unreal project +
`Holodeck.uproject`; gitignored — it is huge and machine-local). It is
**auto-discovered** — no path env var needed. Only the editor is required:

```powershell
$env:UNREAL_EDITOR_EXE = "C:\Program Files\Epic Games\UE_5.3\Engine\Binaries\Win64\UnrealEditor.exe"
```

`discover_custom_engine()` finds the uproject in this order: (1)
`HOLOOCEAN_CUSTOM_ENGINE_PATH` if set (an engine dir *or* a fork root); (2)
the in-project `<repo>/engine`; (3) an `engine/` sibling of the repo.

The fork ships **no packaged binary** (`engine/Binaries/Win64` holds editor
DLLs only), so the engine runs through the UE 5.3 editor:

```powershell
# terminal 1 — engine (stays up; first run compiles shaders)
python scripts\launch_custom_engine.py --clear-cache

# terminal 2 — experiments attach to it (self-contained)
python scripts\sonar_truth_test.py --engine custom --condition BOX --out outputs\demo
```

**Client:** the installed **official HoloOcean 2.3.0 client attaches to the
fork engine** in `-game` mode through `attach_custom_environment(...)`, with
an explicit per-session UUID - verified working. `SpawnAsset`/`ClearSpawned` are engine-side world commands
sent through the generic `Command` API, so no separate fork client is needed.
If a fork client is preferred it can be pinned with
`HOLOOCEAN_CUSTOM_CLIENT_PATH`; otherwise `client_src` is `None` and the
official client is used.

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

The BrineWatch backend does this automatically for `backend.name:
holoocean_custom` (`brinewatch/simulation/custom_engine.py` +
`holoocean_backend.py`): it activates the client (official, or a pinned fork
client) and attaches. Custom-engine scripts run in a fresh process; a loud
`CustomEngineError` is raised on misconfiguration, with **no silent fallback**
to the official engine for acoustic claims.

`clear_octree_cache()` / `launch_custom_engine.py --clear-cache` deletes the
on-disk octree cache for the level before boot, so the sonar octree is
rebuilt from scratch — this rules out a stale cache leaking a previous
session's spawned geometry (the cause of the earlier cross-session REMOVED
anomaly). Every rigorous experiment clears the cache and uses one fresh
engine session per condition.

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

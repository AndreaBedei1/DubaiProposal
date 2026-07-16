# HoloOcean 2.3.0 — verified API facts used by BrineWatch

All facts below were **verified empirically on this machine** (Windows 11,
NVIDIA RTX 6000 Ada, conda env `ocean`, `holoocean==2.3.0`, package `Ocean`
installed) before writing `brinewatch/simulation/holoocean_backend.py`.
Do not rely on features not listed here without re-probing
(`python scripts/inspect_holoocean.py`).

## Environment creation

- `holoocean.make(scenario_cfg=dict, show_viewport=..., verbose=...)` accepts a
  scenario dictionary matching the JSON schema of the installed worlds.
- A custom `scenario_cfg` **must include `"package_name": "Ocean"`**
  (`KeyError: 'package_name'` otherwise — the shipped JSONs omit it, but
  `make()` requires it for custom dicts).
- `"frames_per_sec": false` in the scenario uncaps the sim: measured
  **~76 ticks/s** at `ticks_per_sec: 30` (≈2.5× real time) with rendering on.
- `show_viewport=False` is documented Linux-only; on Windows the window shows.
- Boot time on this machine: ~7 s.
- Worlds in `Ocean` (with usable bounds from `worlds/Ocean/config.json`):
  `SimpleUnderwater` (±70 × ±70 × [-50, 10] m — used by BrineWatch),
  `PierHarbor`, `OpenWater`, `FlatUnderwater`, `Dam`, `Tank`, `Rooms`.
  SimpleUnderwater seabed measured at ≈ −32…−36 m in the central area.

## BlueROV2 agent

- `agent_type: "BlueROV2"` exists (BlueROV2 Heavy, 8 thrusters).
- Control schemes (class docstring order is authoritative; the
  `control_schemes` property list is ordered differently — trust the
  empirical check below):
  - `0`: 8 thruster forces.
  - `1`: **built-in PID controller** taking `[des_x, des_y, des_z, roll, pitch, yaw]`
    (yaw in **degrees**). Verified: command `[5, 5, -12, 0, 0, 0]` from
    `[0, 0, -10]` converges to `[5.12, 5.00, -11.94]` and holds.
  - `2`: global-frame accelerations (custom dynamics; internal dynamics off).
- Commands are numpy float arrays via `env.act(agent_name, cmd)`; states via
  `state = env.tick()` → dict keyed by sensor type names plus `"t"` (sim s).

## Sensors (verified shapes)

| Sensor | Key | Shape / notes |
|---|---|---|
| PoseSensor | `PoseSensor` | (4, 4) homogeneous transform |
| LocationSensor | `LocationSensor` | (3,) `[x, y, z]`, optional `Sigma` noise |
| VelocitySensor | `VelocitySensor` | (3,) |
| DepthSensor | `DepthSensor` | (1,) — returns **z position** (negative down) |
| DVLSensor | `DVLSensor` | (7,) `[vx, vy, vz, r1..r4]` with `ReturnRange: true` |
| RangeFinderSensor | `RangeFinderSensor` | (LaserCount,), `LaserAngle: -90` = down-looking; no hit → negative value |
| IMUSensor | `IMUSensor` | (4, 3) with `ReturnBias: true` |
| ImagingSonar / SidescanSonar / ProfilingSonar / SinglebeamSonar | — | available but octree precompute is expensive; not used in v1 (see assumptions) |

- Sockets used in the shipped JSONs and accepted for BlueROV2: `IMUSocket`,
  `DVLSocket`, `DepthSocket`, `SonarSocket`.

## World interaction

- `env.spawn_prop(prop_type, location, rotation, scale, sim_physics, material, tag)`
  works ("cylinder" verified; "box", "sphere" are standard types). Used to
  build the visible outfall pipe/diffuser. `env.reset()` despawns props —
  the backend therefore avoids gratuitous resets.
- Debug drawing: `env.draw_point`, `draw_line`, `draw_arrow`, `draw_box`
  (used for waypoint visualization).
- `env.weather` / `env.change_weather` exist (unused).
- No `close()` method: HoloOcean kills the engine at interpreter exit; the
  backend calls `__on_exit__()` if present, defensively.

## Coordinate conventions

- Right-handed, z up, metres; underwater z < 0. Rotations `[roll, pitch, yaw]`
  in degrees in scenario configs and PID commands.
- Yaw extracted from PoseSensor rotation block as `atan2(R[1,0], R[0,0])`.

## SimpleUnderwater terrain (measured, v3 live-mission feedback)

- The seabed is NOT flat: measured z between about −29 and −36 across the
  central area — up to ~5 m away from any plane fit. Waypoint depths must
  therefore be commanded as **altitude above the measured bed** (the backend
  does terrain following from the down-looking RangeFinder), never as
  absolute z; and mission arrival checks must be horizontal-only.
- Steep rocky walls surround much of the perimeter: collisions were recorded
  on the slopes near x≈−50 and x≈+49. The usable flat bowl is roughly
  x ∈ [−45, +50], y ∈ [−40, +40] — the live config surveys only that area.
  On a wall, terrain following degenerates into "climbing the cliff"; the
  backend adds a +3 m pop-up escape on contact, and the mission runner
  blacklists stalled waypoints (unreachable spots otherwise keep high GP
  uncertainty and get re-proposed by adaptive planners forever).
- `CollisionSensor` works on the BlueROV2 with `"socket": "COM"` and is part
  of the standard BrineWatch sensor suite; collision events are logged with
  position and count (`scripts/analyze_motion.py` reports them).
- Props are solid: the spawned outfall manifold/risers reach ~2 m above the
  bed and the ROV collides with them when flying below that — the live
  config uses a 3 m survey altitude.

## Known constraints for BrineWatch

- SimpleUnderwater is 140 × 140 m → the demo mixing zone is scaled to 40 m
  (real permits use 100–300 m); all radii/areas are config-driven.
- There is **no water-property (salinity/temperature) field in HoloOcean**;
  the CTD payload samples BrineWatch's analytic plume model at the vehicle
  pose. This is by design (see docs/assumptions.md).
- HoloOcean currents affect vehicle dynamics only if configured; the plume's
  advection is modelled inside the analytic field instead. Vehicle-level
  current forcing is future work.

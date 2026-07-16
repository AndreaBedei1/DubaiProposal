# Environment manifest — verified facts (PFH 2026)

Every entry below was produced by running this probe on the target machine
(`scripts/` equivalent: this file is regenerated, not hand-written).

- Probe executed with: `C:\Users\andrea.bedei3\.conda\envs\ocean\python.exe`
- Python: `3.9.25` (Windows-10-10.0.26200-SP0)
- HoloOcean version: `2.3.0`
- `holoocean.__file__`: `C:\Users\andrea.bedei3\.conda\envs\ocean\lib\site-packages\holoocean\__init__.py`
- Installed packages: `['Ocean']`
- HoloOcean data root: `C:\Users\andrea.bedei3\AppData\Local\holoocean\2.3.0`
- Ocean package version: `2.3.0`
- Available worlds: `['Rooms', 'ModernOffice', 'CorporateOffice', 'ExampleLevel', 'Tank', 'SimpleUnderwater', 'PierHarbor', 'OpenWater', 'FlatUnderwater', 'Dam']`
- Sonar sensor classes present in installed package: `['ImagingSonar', 'ProfilingSonar', 'SidescanSonar', 'SinglebeamSonar']`
- Camera/capture sensors present: `['RGBCamera', 'ViewportCapture', 'DepthCamera']`
- BlueROV2 agent present: `True` (agent_type='BlueROV2')
- Octree management API at package top level: `['delete_all_octrees', 'delete_world_octrees']`
  - `holoocean.delete_all_octrees()`
  - `holoocean.delete_world_octrees(world_name)`
- `HoloOceanEnvironment.spawn_prop(self, prop_type, location=None, rotation=None, scale=1, sim_physics=False, material='', tag='')`
- Debug drawing methods: `['draw_arrow', 'draw_box', 'draw_debug_vector_field', 'draw_line', 'draw_point']`
- Agent teleport available: `True`
- GPU (nvidia-smi): `NVIDIA RTX 6000 Ada Generation, 49140 MiB, 596.59`

## Verified runtime behaviour (from executed smoke tests, this machine)

- Custom `scenario_cfg` dicts REQUIRE the `package_name` key (KeyError otherwise).
- BlueROV2 `control_scheme=1` is the built-in PID `[x, y, z, roll, pitch, yaw(deg)]`
  (verified empirically by convergence test; the `control_schemes` property list
  order is misleading — trust the class docstring order).
- `frames_per_sec: false` uncaps the sim (~2.3-2.5x real time on this GPU).
- `env.spawn_prop(...)` works at runtime ('cylinder', 'box' verified).
- `env.reset()` despawns runtime props.
- SimpleUnderwater seabed is uneven (measured z in [-36, -29] centrally) with
  steep rocky perimeter walls; flat bowl approx x in [-45, 40], y in [-28, 40].
- CollisionSensor works on BlueROV2 with socket 'COM'.

## Exact commands that start the current simulation

```powershell
& "C:\Users\andrea.bedei3\.conda\envs\ocean\python.exe" scripts/run_mission.py --config configs/mission_default.yaml   # kinematic
& "C:\Users\andrea.bedei3\.conda\envs\ocean\python.exe" scripts/run_mission.py --config configs/holoocean_live.yaml   # HoloOcean live
& "C:\Users\andrea.bedei3\.conda\envs\ocean\python.exe" scripts/run_benchmark.py --config configs/benchmark.yaml --seeds 5
& "C:\Users\andrea.bedei3\.conda\envs\ocean\python.exe" -m pytest tests -q
```

All BrineWatch code uses ONLY the official, unmodified HoloOcean installation
above and the official Ocean package. No engine patches, no custom worlds, no
runtime octree-refresh mechanisms beyond the official public API listed here.

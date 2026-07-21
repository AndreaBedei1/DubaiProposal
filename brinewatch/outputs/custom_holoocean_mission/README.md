# End-to-end custom-HoloOcean mission, collision-safe (Phase 2)

The genuinely end-to-end custom-engine demo: **motion AND sensing in the fork**.
The BlueROV2 is driven through the whole survey inside the custom HoloOcean
engine (runtime octree rebuild), with a collision-safe navigation layer keeping
a standoff from the localized structure. The earlier
`run_custom_pfh2026_demo.py` kept the survey kinematic precisely because
"driving the real ROV through the spawned structure collides" — that limitation
is removed here.

Reproduce (engine first):

```bash
python scripts/launch_custom_engine.py --clear-cache            # terminal 1
python scripts/run_custom_holoocean_mission.py \
    --ring-poses 16 --budget 220 --prior-x 42 --prior-y 2       # terminal 2
```

## `run1/` — flagship run (2026-07-21)

Single fork-engine session: terrain probe → baseline sonar ring (no outfall) →
spawn the 105-component multiport outfall → inspection sonar ring
(pipe/diffuser/risers) → LOCATE → drive to a safe start → **BASELINE + adaptive
SURVEY in-engine, collision-safe** → screening + report.

| quantity | value |
|----------|------:|
| survey backend | **holoocean_custom (BlueROV2 driven in-engine)** |
| sonar LOCATE error vs true diffuser centre (39.8, 0) | **1.65 m** |
| CTD samples along the engine trajectory | 271 |
| travel budget used | 220 m |
| **collisions (engine flag)** | **0** |
| collision-safe detours taken | 2 |
| **minimum structure clearance** | **3.49 m** (standoff 2.0 m) |
| screening | REVIEW |

### LOCATE (no ground truth)

Background subtraction (pre-installation baseline vs inspection at the same
poses) cancels common clutter; the residual frames are fed to the in-situ
**diffuser-line** locator, which fits the pipeline bearing and takes the
along-track midpoint of the inlier risers. This rejects an off-axis spawned
scene element (rock berm at ≈ (55, 20)) that the plain densest-cluster
consensus locked onto (`background_only_estimate` in `locate_result.json` is
≈ 4.5 m; the line fit reaches **1.65 m**). Ground truth is used only to score.

### Why this matters for real-world feasibility

- **0 collisions in-engine** with a correctly-placed hazard field: the standoff
  (built from the 1.65 m sonar estimate + the design chart, no GT) kept the ROV
  ≥ 3.49 m from the pipe / diffuser / risers throughout, while still collecting
  271 CTD samples of the plume.
- The coupling is honest and documented: collision-safe navigation is only as
  good as the localization. An earlier run with a far-off prior (14 m) localized
  the rock instead of the diffuser (25 m error) → the hazard field was misplaced
  and the ROV stalled near the real structure (reactive stall detection still
  prevented a collision). Centering the ring on a realistic chart prior +
  the diffuser-line filter fixes it (this run).

## Files

| file | content |
|------|---------|
| `summary.json` | all metrics (see `CUSTOM_MISSION_OK` for the flat extras) |
| `locate_result.json` | sonar estimate, inliers, axis, σ, background-only estimate |
| `map_truth_vs_reconstruction.png` | GT plume · GP mean + engine trajectory + samples · GP std |
| `map_compliance.png` | screening / compliance map |
| `report.html` | full digital-twin mission report |
| `scene_manifest.json` | the 105 spawned outfall components (world positions) |
| `mission_log.jsonl` | event log incl. `safe_detour` events |
| `samples.csv`, `plume_maps.npz`, `terrain.npz`, `config_used.yaml` | data |

The plume/CTD salinity field is the documented analytic **simulation surrogate**,
sampled along the real engine trajectory; the sonar, the vehicle motion and the
collision flags are the engine. Collision-safe navigation module:
`brinewatch/planning/safe_nav.py` (engine-free tests in `tests/test_safe_nav.py`,
`tests/test_safe_nav_mission.py`).

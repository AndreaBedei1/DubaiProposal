# BrineWatch

**Uncertainty-aware screening of desalination brine plumes with a low-cost
ROV — an Initial Prototype in the official HoloOcean simulator.**

A BlueROV2 localizes an outfall structure from imaging-sonar contacts
(starting from an approximate chart position — the mission never receives
the true location), samples the near-bed salinity field with a virtual
conductivity–temperature payload, reconstructs it with a Gaussian process,
and issues a three-state screening result — **CLEAR / REVIEW / POSSIBLE
EXCEEDANCE** — against a configurable mixing zone. Every mission produces a
self-contained digital report; repeated missions build a site history.

This is a research prototype: the plume is a documented analytic surrogate
(not CFD), water properties are virtual, and screening is not regulatory
certification. The full honesty ledger lives in
[docs/assumptions.md](docs/assumptions.md) and
[docs/application/pfh2026/LIMITATIONS.md](docs/application/pfh2026/LIMITATIONS.md).

## One-command demos

```bash
# inside the conda env (HoloOcean 2.x + Ocean package for the live demos)
pip install -e .

# --- engine-free (no GPU, seconds to ~1 min) ------------------------------
python -m pytest tests -q                                   # 142 tests, no GPU needed
python scripts/run_mission.py --config configs/mission_default.yaml          # kinematic demo
python scripts/run_benchmark.py --config configs/benchmark_static.yaml  --seeds 12 --seed-start 100
python scripts/run_benchmark.py --config configs/benchmark_dynamic.yaml --seeds 12 --seed-start 100
python scripts/run_volumetric_mission.py --planner adaptive                  # 3-D plume reconstruction
python scripts/compare_localization_modes.py                                 # in-situ vs background sonar
python scripts/build_site_history_demo.py                                    # simulated repeated-mission campaign
python scripts/build_dashboard.py                                            # self-contained digital-twin dashboard
python scripts/make_mission_movie.py --run outputs/<custom_run> --rgb outputs/<cinematic>/frames  # demo MP4

# --- custom HoloOcean fork (GPU; launch the engine first) -----------------
export UNREAL_EDITOR_EXE=".../UE_5.3/Engine/Binaries/Win64/UnrealEditor.exe"
python scripts/launch_custom_engine.py --clear-cache --level ExampleLevel    # terminal 1
python scripts/run_custom_holoocean_mission.py \
    --ring-poses 16 --budget 220 --prior-x 42 --prior-y 2                     # terminal 2: in-engine, collision-safe
python scripts/run_custom_pfh2026_demo.py                                     # custom sonar LOCATE + kinematic survey

# --- official HoloOcean (GPU) ---------------------------------------------
python scripts/run_pfh2026_demo.py                          # official HoloOcean mission (~20 min)
python scripts/validate_sonar_visibility.py                 # acoustic-visibility experiment
```

The flagship end-to-end demonstration is `scripts/run_custom_holoocean_mission.py`
(motion + sonar in the custom fork, collision-safe survey); the demonstration
video is `outputs/video_demo/mission_movie/mission_movie.mp4`. All application
material is under [docs/application/pfh2026/](docs/application/pfh2026/).

## Current evidence (verified on this repository)

- **Planner benchmark** (20 held-out seeds × 2 planners × 2 field families,
  equal budget, identical LOCATE/BASELINE): adaptive boundary-aware sampling
  cuts in-plume RMSE by 11–15 % and lifts boundary F1 by up to +17 % when the
  budget cannot densely cover the site (25–50 % budget); the lawnmower
  matches or wins once coverage saturates. Full numbers:
  [BENCHMARK_REPORT](docs/application/pfh2026/BENCHMARK_REPORT.md).
- **Screening**: zero wrong conclusive results in 320 evaluations; every
  near-margin case became an explicit REVIEW instead of a coin-flip verdict.
- **Sonar**: runtime-spawned props are provably invisible to the official
  acoustic octree (bit-identical present/absent frames); official stock
  structures return strong echoes (open-water control: zero); under mission
  noise, single-ping intensity does not separate structure from clutter
  (measured on 538 recorded frames), so localization uses multi-aspect
  spatial persistence. Details:
  [SONAR_VALIDATION](docs/application/pfh2026/SONAR_VALIDATION.md).
- **Official HoloOcean mission** (PierHarbor, BlueROV2, no ground-truth
  access): sonar LOCATE resolved the outfall structure complex with ~6 m
  error from a 17 m chart prior in ~110 m of travel; full mission completes
  with terrain calibration at 0.06–0.12 m plane RMSE.
- **Simulated site history**: a 6-mission discharge ramp is tracked
  CLEAR → REVIEW → POSSIBLE EXCEEDANCE
  ([trend](docs/application/pfh2026/assets/results/site_history_trend.png),
  clearly labelled simulated).

### Custom-fork engine (runtime octree rebuild)

The official acoustic octree is static, so runtime-spawned props are invisible
to it (finding above). A custom HoloOcean fork rebuilds the octree on spawn,
making the **actual** spawned outfall sonar-visible — which unlocks a genuinely
end-to-end mission:

- **In-engine collision-safe mission** (`outputs/custom_holoocean_mission/`):
  the BlueROV2 is driven through the whole survey *inside* the fork; sonar
  LOCATE **1.65 m** (background subtraction + diffuser-line fit, no GT),
  271 in-engine CTD samples, **0 collisions**, min structure clearance 3.49 m
  (2 m standoff from a hazard field built from the estimate + design chart).
- **In-situ single-mission localization** (`outputs/localization/compare/`): a
  no-baseline mode robust to clutter (2–6 m where background subtraction blows
  out to 10.8 m), with bootstrap uncertainty.
- **3-D volumetric plume** (`outputs/volumetric/`): multi-altitude survey →
  terrain-following x-y-z GP → slices + iso-surface + volume.
- **Digital-twin dashboard** (`outputs/dashboard/index.html`): a single
  self-contained HTML page — latest verdict, per-mission maps + KPIs, site
  trends; also the exportable report.
- **Demonstration MP4** (`outputs/video_demo/mission_movie/`): a ~28 s
  walk-through assembled from the real mission outputs.

See [CUSTOM_ENGINE](docs/application/pfh2026/CUSTOM_ENGINE.md),
[CUSTOM_LOCALIZATION_STUDY](docs/application/pfh2026/CUSTOM_LOCALIZATION_STUDY.md)
and `outputs/experiments/README.md` (consolidated validation results).

## What is simulated

Vehicle, terrain, cameras and sonar: official HoloOcean 2.3.0 (unmodified) —
plus a fast kinematic twin for statistics. Salinity/temperature: an analytic
plume surrogate sampled at the vehicle pose (HoloOcean has no water
properties). The sonar detector's thresholds are tuned on simulated
acoustics and will need re-tuning on the physical sonar. Localization
targets are stock world structures (see the octree finding above); the
spawned outfall geometry is visual/collision only.

## What remains before field deployment

1. MAVLink/ArduSub backend (the mission layer is backend-agnostic by
   design — see [docs/sim_to_real.md](docs/sim_to_real.md));
2. physical CT payload retrofit + bench calibration
   ([protocol](docs/application/pfh2026/PHYSICAL_VALIDATION_PROTOCOL.md));
3. one-day controlled water test (salinity gradient, reference casts);
4. harbour trial at a natural salinity anomaly; 5. real-outfall pilot with
   a utility/regulator partner. No field data exists yet; nothing here is
   certified monitoring.

## Repository map

```
brinewatch/
├── brinewatch/          mission stack (simulation/, perception/, sensors/,
│                        plume/, planning/, mapping/, mission/, evaluation/,
│                        visualization/, utils/)
├── configs/             mission, benchmark and PFH-2026 scenario configs
├── scripts/             demos, benchmarks, sonar experiments, scene tools
├── tests/               142 tests incl. real recorded-sonar fixtures
├── docs/                architecture, assumptions, HoloOcean notes, sim-to-real
├── docs/application/pfh2026/   application evidence package
└── site_history/        longitudinal screening ledger (simulated demo)
```

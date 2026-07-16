# BrineWatch architecture

BrineWatch simulates an autonomous BlueROV2 mission that locates a
desalination outfall, surveys the brine discharge zone, reconstructs the 3-D
salinity field with a Gaussian process, and issues a mixing-zone compliance
verdict — then benchmarks a fixed lawnmower survey against adaptive
informative sampling at *equal travel budget*.

Companion documents:

- [`docs/assumptions.md`](assumptions.md) — the honesty ledger: every
  approximation, why it exists, and its impact.
- [`docs/sim_to_real.md`](sim_to_real.md) — roadmap from this simulation to a
  real BlueROV2.
- [`docs/holoocean_notes.md`](holoocean_notes.md) — empirically verified
  HoloOcean 2.3.0 API facts the HoloOcean backend relies on.

## Module map

```
brinewatch/
├── utils/               Shared foundations (no brinewatch-internal deps)
│   ├── types.py         Value types: Waypoint, VehicleState, CTDSample,
│   │                    Detection, MissionBudget, MissionPhase, MissionResult
│   ├── config.py        Typed config dataclass tree + YAML loader
│   │                    (unknown keys raise — typos fail loudly)
│   ├── geometry.py      wrap_angle, heading_to, dist2/dist3,
│   │                    expanding_square (SAR search), boustrophedon
│   └── logging_utils.py MissionLogger (JSONL events), run dirs, CSV/JSON dumps
│
├── simulation/          Vehicle & world backends (the ONLY simulator-aware code)
│   ├── base.py          SimulatorBackend ABC — the frozen backend contract
│   ├── kinematic.py     KinematicBackend: first-order kinematics, no deps, fast
│   ├── holoocean_backend.py
│   │                    HoloOceanBackend: native BlueROV2 in HoloOcean 2.x,
│   │                    PID position control, outfall props, debug drawing
│   └── __init__.py      make_backend() factory ("kinematic" | "holoocean";
│                        holoocean imported lazily so it is never required)
│
├── plume/               Ground truth
│   └── model.py         BrinePlume: analytic salinity/temperature field
│                        (ambient stratification + near-field jets + far-field
│                        gravity current + tidal advection). NOT CFD — see
│                        assumptions ledger, item 1.
│
├── sensors/             Virtual payloads
│   ├── ctd.py           VirtualCTD: rate-limited sampling of the analytic
│   │                    field at the vehicle pose + Gaussian sensor noise
│   └── locator.py       DiffuserLocator: probabilistic range/bearing
│                        detection model of the diffuser (not a sonar sim)
│
├── mapping/             Field reconstruction
│   ├── gp_mapper.py     GPMapper: exact GP regression, anisotropic RBF
│   │                    (xy vs z length scales), ambient profile as prior
│   │                    mean, fixed hyperparameters, chunked prediction
│   └── grid_map.py      EvalGrid: 2.5-D near-bottom lattice
│                        (z = seabed(x, y) + altitude) for evaluation/plots
│
├── planning/            Survey strategies
│   ├── base.py          Planner ABC: next_waypoint(state, mapper, budget)
│   ├── lawnmower.py     LawnmowerPlanner: fixed boustrophedon baseline
│   └── adaptive.py      AdaptivePlanner: greedy GP-based informative
│                        sampling (posterior std + compliance-boundary bonus
│                        − travel cost)
│
├── mission/             Orchestration
│   └── runner.py        MissionRunner state machine
│                        (LOCATE → BASELINE → SURVEY → DONE), budget owner,
│                        boundary_salinity_psu(), build_planner(),
│                        create_mission() factory
│
├── evaluation/          Scoring against ground truth
│   ├── metrics.py       compute_metrics(): RMSE (all / in-plume), MAE,
│   │                    boundary F1/IoU, coverage, in-plume sample fraction
│   ├── compliance.py    evaluate_compliance(): mixing-zone verdict with
│   │                    uncertainty-aware P(exceed) from the GP std
│   └── benchmark.py     run_benchmark(): lawnmower vs adaptive, multi-seed,
│                        metrics at equal-budget checkpoints, CSV + JSON out
│
└── visualization/       Reporting
    ├── plots.py         Truth-vs-reconstruction maps, learning curves,
    │                    compliance/exceedance map (Agg backend, PNG files)
    └── report.py        render_html_report(): self-contained digital-twin
                         style HTML report (base64-embedded figures)

scripts/
├── run_mission.py       One mission end-to-end → maps, verdict, HTML report
├── run_benchmark.py     Equal-budget lawnmower-vs-adaptive comparison
└── inspect_holoocean.py Sanity-check the local HoloOcean install (optional)

configs/
├── mission_default.yaml Kinematic backend, adaptive planner (the demo)
├── benchmark.yaml       Benchmark run (kinematic, both planners, checkpoints)
└── holoocean_live.yaml  Live HoloOcean mission (BlueROV2, SimpleUnderwater)
```

Dependency direction is strictly downward: `utils` depends on nothing
internal; `plume`, `sensors`, `mapping`, `planning`, `simulation` depend only
on `utils` (and `sensors`/`planning` on `plume`/`mapping` types);
`mission` wires everything together; `evaluation` and `visualization` consume
mission outputs. Nothing outside `brinewatch/simulation/holoocean_backend.py`
imports `holoocean`, and that import is lazy.

## The SimulatorBackend abstraction

`brinewatch/simulation/base.py` defines the whole surface the mission layer
sees of any vehicle, simulated or real:

```python
class SimulatorBackend(abc.ABC):
    name: str                     # property: backend identifier
    control_period_s: float       # property: seconds advanced per step
    def reset(self) -> VehicleState: ...
    def step_toward(self, waypoint: Waypoint) -> VehicleState: ...
    def close(self) -> None: ...  # optional resource release
```

The contract (binding, documented in the ABC docstring):

- `reset()` (re)initializes the vehicle and returns its initial state.
- `step_toward(wp)` advances the world by **exactly one control period** of
  simulated time while steering toward the waypoint, and returns the new
  `VehicleState` (position, attitude, velocity, altitude above seabed).
- Backends do **not** track budget, samples, or mission phase — the
  `MissionRunner` owns all of that, and computes travelled distance itself
  from consecutive reported positions.

Two implementations exist:

- `KinematicBackend` — first-order velocity dynamics with separate
  horizontal/vertical speed limits and optional Gaussian position noise.
  No rendering, no external dependencies; benchmarks over many seeds run in
  seconds. This is the default and the only backend the test suite exercises.
- `HoloOceanBackend` — drives the native BlueROV2 agent in HoloOcean 2.x
  using the built-in PID position controller (`control_scheme=1`), reads
  Pose/Location/Velocity/Depth/DVL/RangeFinder sensors, spawns visible
  outfall props, and enforces a minimum-altitude safety floor when commanding
  depth. Every API fact it relies on was verified on the target machine — see
  [`docs/holoocean_notes.md`](holoocean_notes.md).

### Why the mission layer is simulator-agnostic

`MissionRunner`, the planners, the mapper, and the sensors only ever exchange
the value types in `brinewatch/utils/types.py` (`VehicleState` in,
`Waypoint` out). Consequences:

1. **Fair benchmarking.** The lawnmower-vs-adaptive comparison runs on the
   fast kinematic backend with identical mission logic to the HoloOcean demo;
   only the vehicle response differs.
2. **No engine tax during development.** Everything except the HoloOcean
   backend itself imports, runs, and is testable without a GPU or the
   HoloOcean engine installed.
3. **Sim-to-real by construction.** A future `MAVLinkBackend` speaking to a
   real BlueROV2 (or ArduSub SITL) implements the same four members and the
   entire mission stack — runner, planners, mapper, compliance, report —
   transfers unchanged. That path is spelled out in
   [`docs/sim_to_real.md`](sim_to_real.md).

## Data flow

Control loop (one iteration per backend control period):

```
                 (1) VehicleState
  +--------------------+ ------------------> +---------------------------+
  |  SimulatorBackend  |                     |       MissionRunner       |
  |  kinematic / holo- | <------------------ |  LOCATE -> BASELINE ->    |
  |  ocean (or MAVLink)|  (5) step_toward    |  SURVEY -> DONE           |
  +--------------------+     (Waypoint)      |  owns MissionBudget       |
                                             +------+-------------+------+
                                                    | (2) state   | (2') ping
                                                    v             v (LOCATE only)
+------------+  true field  +------------+   +-------------+  +-----------------+
| BrinePlume | -----------> | VirtualCTD |   |  GPMapper   |  | DiffuserLocator |
| (analytic  |              | (noise, at |-->| add_sample  |  | range/bearing   |
|  ground    |              |  ctd rate) |(3)| (online GP) |  | detections      |
|  truth)    |              +------------+   +------+------+  +-----------------+
+------------+                                      | (4) posterior mean/std
                                                    v
                                             +-------------+
                                             |   Planner   |
                                             | lawnmower / |
                                             |  adaptive   |
                                             +------+------+
                                                    | next Waypoint
                                                    +--> back to MissionRunner
```

Post-mission (offline):

```
MissionResult (samples, budget_at_sample, trajectory, detections,
               outfall_estimate, phase_history, notes)
      |
      |   EvalGrid (near-bottom lattice)     BrinePlume.ground_truth(grid, t=0)
      |   GPMapper.predict(grid.points) -> (mean, std)
      v
+---------------------------- evaluation ----------------------------+
| metrics.compute_metrics(mean, truth, ...)   -> MetricsResult       |
| compliance.evaluate_compliance(mean, std, ...) -> ComplianceVerdict|
| benchmark.run_benchmark(...)  (multi-seed, equal-budget            |
|                                checkpoints via samples_within_budget)|
+----------------------+----------------------------------------------+
                       v
        visualization.plots  (truth-vs-reconstruction map,
                              compliance map, learning curves -> PNG)
                       |
                       v
        visualization.report.render_html_report
        (self-contained HTML: verdict banner, stats, figures,
         metrics, approximations section)
```

Key invariants of the loop:

- The **runner owns the budget**: after every `step_toward` it consumes the
  3-D distance actually travelled (`utils.geometry.dist3` between consecutive
  reported positions) and hard-stops mid-leg when the budget is exhausted.
- The **CTD is rate-limited** (`VirtualCTD.maybe_sample`), so sample density
  depends on vehicle speed and backend control period, exactly like a real
  1 Hz payload.
- Every accepted sample goes to both `MissionResult.samples` (with the budget
  reading at that instant, enabling equal-budget replays) and
  `GPMapper.add_sample` (so the adaptive planner always sees the latest
  posterior).
- LOCATE (expanding-square search with locator pings, capped at
  `budget.locate_fraction`) and BASELINE (two crossing transects through the
  outfall estimate) are identical for every planner; strategies differ only
  in SURVEY, at equal total budget.

## Frozen-interface contracts

The public signatures below are frozen; their docstrings are the binding
behaviour spec. Implementations may add private helpers but must not change
names, parameters, defaults, or return types.

| Contract | Where | Essence |
|---|---|---|
| `SimulatorBackend` | `simulation/base.py` | `reset`/`step_toward` advance exactly one `control_period_s`; backends never track budget or samples. |
| `Planner.next_waypoint(state, mapper, budget)` | `planning/base.py` | Return the next `Waypoint` or `None` to end the survey; must be budget-aware (the runner still hard-stops regardless). |
| `LawnmowerPlanner` | `planning/lawnmower.py` | Precomputed boustrophedon corners at `seabed + altitude`; ignores the mapper; deterministic. |
| `AdaptivePlanner` | `planning/adaptive.py` | Seeded random candidates scored by `weight_std * std + weight_boundary * exp(-|mean − boundary|/scale) − weight_travel * dist`; min-separation from visited points; warmup exploration below `warmup_samples`. |
| `GPMapper.add_sample / predict` | `mapping/gp_mapper.py` | Exact GP on salinity *anomaly* with ambient prior mean; fixed hyperparameters; seeded subsampling above `max_train_points`; `predict` returns `(mean, std)` of absolute salinity. |
| `compute_metrics(...) -> MetricsResult` | `evaluation/metrics.py` | RMSE/MAE, boundary F1/IoU against `truth > threshold`, coverage fraction, in-plume sample fraction. |
| `evaluate_compliance(...) -> ComplianceVerdict` | `evaluation/compliance.py` | Mixing-zone rule outside `mixing_zone_radius_m`; `std=None` scores a noiseless field; `prob_exceed_max` is the uncertainty-aware verdict. |
| `run_benchmark(...) -> BenchmarkResult` | `evaluation/benchmark.py` | Per seed × planner missions via `create_mission(seed_offset=...)`; fresh GP refit per budget checkpoint via `MissionResult.samples_within_budget`; flat record dicts + CSV/JSON artifacts. |
| Plot functions | `visualization/plots.py` | Agg backend, save PNG to `path`, return `path`; flattened arrays aligned with `EvalGrid.points`. |
| `render_html_report(...)` | `visualization/report.py` | Single self-contained HTML file, base64-embedded figures, verdict banner, approximations section. |
| Config schema | `utils/config.py` | One dataclass per module; YAML loading rejects unknown keys; `load_config(path, overrides)` deep-merges overrides. |
| `MissionResult` | `utils/types.py` | `budget_at_sample[i]` is the budget consumed when `samples[i]` was taken — the hook that makes equal-budget comparison possible. |

## How to extend

### Adding a new planner

1. Create `brinewatch/planning/my_planner.py` with a class subclassing
   `planning.base.Planner`; set the class attribute `name` and implement
   `next_waypoint(state, mapper, budget)`. Return waypoints at
   `z = seabed_fn(x, y) + survey.altitude_m` (both existing planners fly the
   same altitude — that is what keeps comparisons fair), and return `None`
   when done or when the remaining budget makes another leg pointless.
2. Any tunables go in a new dataclass in `brinewatch/utils/config.py`, added
   as a field of `MissionConfig` (unknown YAML keys already fail loudly).
3. Register the planner in `build_planner()` in
   `brinewatch/mission/runner.py` and export it from
   `brinewatch/planning/__init__.py`.
4. It is now selectable via `planner: my_planner` in YAML or
   `--planner my_planner` in `scripts/run_mission.py`, and benchmarkable by
   adding its name to the `planners` sequence of
   `evaluation.benchmark.run_benchmark`.

Use randomness only through `numpy.random.default_rng(seed)` with a seed
passed into the constructor (see `AdaptivePlanner` and how
`build_planner` derives its seed from `cfg.seed`).

### Adding a new backend

1. Create `brinewatch/simulation/my_backend.py` subclassing
   `SimulatorBackend`. Implement `name`, `control_period_s`, `reset`,
   `step_toward`, and `close` if there are resources to release. Optionally
   provide `draw_waypoint(wp)` — the runner calls it via duck typing when
   present (see `_phase_survey` in `mission/runner.py`).
2. Honour the contract: one control period per `step_toward` call, report
   positions in the world frame (z up, negative underwater), fill
   `VehicleState.altitude` if you can measure height above the seabed
   (the HoloOcean backend uses it as a depth-command safety floor).
3. Add a config dataclass to `utils/config.py` and a field on
   `BackendConfig`; register the backend name in `make_backend()` in
   `brinewatch/simulation/__init__.py`. Import heavyweight dependencies
   lazily inside the constructor, as `HoloOceanBackend` does with
   `holoocean`, so the rest of the package never pays for them.
4. Nothing else changes: `create_mission(backend_name=...)` and the
   `--backend` CLI flag pick it up through the factory.

The most valuable future backend is a MAVLink one targeting a real
BlueROV2 — the concrete plan is in [`docs/sim_to_real.md`](sim_to_real.md).

# BrineWatch

**Autonomous monitoring of desalination brine plumes with a BlueROV2 in
HoloOcean.** A simulated BlueROV2 Heavy locates a desalination outfall on the
seabed, surveys the discharge zone with a CTD payload, reconstructs the 3-D
salinity field with a Gaussian process, checks it against a mixing-zone
compliance threshold, and renders a digital-twin style HTML report — then
benchmarks **fixed lawnmower vs adaptive informative sampling at equal travel
budget**.

The plume is a **synthetic analytic field** (dense-jet rise + bottom gravity
current + tidal advection), *not* CFD — by construction, so the exact ground
truth is known and sampling strategies can be scored quantitatively. Every
approximation is documented in [docs/assumptions.md](docs/assumptions.md).

## Headline result (5 seeds, equal budget, kinematic backend)

| Budget used | RMSE in plume (PSU) — lawnmower | — adaptive | Boundary F1 — lawnmower | — adaptive |
|---|---|---|---|---|
| 25 % (400 m) | 1.27 ± 0.27 | **0.93 ± 0.03** | 0.50 | 0.49 |
| 50 % (800 m) | 1.20 ± 0.21 | **0.92 ± 0.21** | 0.50 | **0.66** |
| 75 % (1200 m) | 0.86 ± 0.13 | **0.68 ± 0.11** | 0.61 | 0.65 |
| 100 % (1600 m) | **0.55 ± 0.04** | 0.74 ± 0.07 | 0.67 | 0.66 |

Adaptive sampling wins clearly **when the budget is scarce** (-21…-26 % RMSE,
+32 % boundary F1 at half budget); the blanket lawnmower catches up only once
1600 m suffices to cover the whole 120×120 m box at 10 m line spacing. Both
strategies produced the correct compliance verdict in 10/10 missions.
Reproduce with `python scripts/run_benchmark.py --seeds 5`.

## Live HoloOcean missions (BlueROV2 in SimpleUnderwater)

Full autonomous missions on the real simulator (RTX-class GPU, ~2.5× real
time): the ROV localizes the physically-spawned diffuser with the sonar-like
locator (**0.8 m error after ~10 m of travel**), then surveys with terrain
following over uneven terrain. Best run (1100 m budget, 7.4 min wall):
**RMSE in plume 0.555 PSU — matching the kinematic gold standard — boundary
F1 0.81, coverage 0.91**, zero stalls, 0 % idle time, ~1 m/s throughout.

Two field lessons the live runs taught (both documented in
[docs/assumptions.md](docs/assumptions.md) / [docs/holoocean_notes.md](docs/holoocean_notes.md)):

- **Survey altitude must match the compliance layer**: flying at 3 m above
  the bed samples a ~3.5× weaker brine layer than the 1 m evaluation
  altitude and biases the verdict toward PASS; the live profile flies 2.2 m.
- **At fine margins, read the probability, not the binary verdict**: when the
  true exceedance is a few tenths of a PSU, a budget-limited mission may
  reconstruct PASS — but with P(exceed) ≈ 0.3-0.4, which correctly reads as
  *inconclusive: do not certify, resurvey*. That is what the
  uncertainty-aware output is for.

## Installation

Prerequisites: Python ≥ 3.9 with numpy/scipy/matplotlib/PyYAML. For the
HoloOcean backend (optional): [HoloOcean 2.x](https://byu-holoocean.github.io/holoocean-docs/)
with the `Ocean` package installed and a discrete GPU. The kinematic backend
has **no external dependencies** — everything except the live 3-D simulation
works without HoloOcean.

```bash
# inside your (conda) environment — e.g. the one where HoloOcean lives
pip install -e .
pip install pytest             # for the test suite

# sanity-check the HoloOcean installation (optional)
python scripts/inspect_holoocean.py           # add --launch for a boot test
```

## Quickstart

```bash
# 1) Demo mission: adaptive planner on the fast kinematic backend (~1 min)
python scripts/run_mission.py --config configs/mission_default.yaml

# 2) The same mission with the other strategy
python scripts/run_mission.py --planner lawnmower

# 3) Equal-budget benchmark, 5 seeds x 2 planners (~3 min)
python scripts/run_benchmark.py --config configs/benchmark.yaml --seeds 5

# 4) Live HoloOcean mission: BlueROV2 in SimpleUnderwater (~10-15 min, GPU)
python scripts/run_mission.py --config configs/holoocean_live.yaml

# 5) Tests (65 tests, ~2 min; no HoloOcean needed)
python -m pytest tests -q

# 6) Motion-quality feedback on the latest run (stalls, zig-zag, collisions)
python scripts/analyze_motion.py
```

Every mission writes a timestamped folder under `outputs/`.

## What a mission does

```
LOCATE    expanding-square search around the a-priori outfall position;
          a sonar-like locator confirms the diffuser (range/bearing)
BASELINE  two crossing transects through the outfall estimate
SURVEY    planner-driven sampling until the travel budget is exhausted
            - lawnmower: precomputed boustrophedon over the survey box
            - adaptive:  greedy GP-based informative sampling, drawn toward
                         high uncertainty and the compliance isohaline
REPORT    GP reconstruction -> metrics -> mixing-zone verdict -> report.html
```

## Interpreting the outputs

| File | Meaning |
|---|---|
| `report.html` | Self-contained digital-twin snapshot: verdict banner (PASS/FAIL vs ground truth), mission stats, maps, metrics, and the approximations ledger |
| `map_truth_vs_reconstruction.png` | Ground truth vs GP mean (with trajectory + samples) vs GP uncertainty |
| `map_compliance.png` | Exceedance above the threshold, mixing-zone circle, worst point |
| `samples.csv` | Every CTD sample with position, salinity, temperature, budget stamp |
| `plume_maps.npz` | Mean/std/truth fields + grid — the raw digital twin layer |
| `mission_log.jsonl` | Timestamped event log (phases, detections, warnings) |
| `summary.json` | One-look mission summary (verdict, errors, sample counts) |
| `benchmark_records.csv` / `benchmark_summary.json` / `learning_curves.png` | Per-seed records, per-checkpoint aggregates, and error-vs-budget curves |

Key metrics: `rmse_plume` (reconstruction error where the plume actually is),
`boundary_f1` (how well the compliance isohaline is localized),
`coverage_frac` (area within 8 m of a sample), `verdict_correct`
(reconstructed PASS/FAIL matches ground truth). Read `prob_exceed_max`
alongside the binary verdict: PASS with P(exceed) ≳ 0.2 means *inconclusive —
resurvey*, not *compliant*.

## What is realistic vs approximated

Realistic: BlueROV2 vehicle and its built-in PID control in HoloOcean (Fossen
dynamics in the engine), sensor suite geometry (DVL, depth, IMU, down-looking
rangefinder for altitude), noise models on CTD/locator/navigation, equal-budget
mission logic, GP reconstruction and the compliance rule structure.

Approximated (full ledger in [docs/assumptions.md](docs/assumptions.md)):
the plume is an analytic surrogate (not CFD); the CTD samples that analytic
field because HoloOcean has no water properties; the diffuser locator is a
detection model, not simulated acoustics; the mixing zone is scaled to 40 m
(real permits: 100-300 m) to fit the 140 m world; battery = travelled metres;
GP hyperparameters are fixed.

## Project structure

```
brinewatch/
├── brinewatch/
│   ├── simulation/     SimulatorBackend ABC + kinematic & HoloOcean backends
│   ├── plume/          Analytic brine plume ground truth
│   ├── sensors/        Virtual CTD payload + diffuser locator
│   ├── planning/       Lawnmower + adaptive informative planners
│   ├── mapping/        GP field reconstruction + evaluation grid
│   ├── mission/        LOCATE/BASELINE/SURVEY state machine + factory
│   ├── evaluation/     Metrics, mixing-zone compliance, benchmark harness
│   ├── visualization/  Matplotlib figures + self-contained HTML report
│   └── utils/          Types, YAML config schema, geometry, logging
├── configs/            mission_default / holoocean_live / benchmark YAMLs
├── scripts/            run_mission.py, run_benchmark.py, inspect_holoocean.py
├── tests/              65 tests, all runnable without HoloOcean
└── docs/               architecture, assumptions, HoloOcean notes, sim-to-real
```

Design rule: the mission layer only sees the `SimulatorBackend` interface —
which is what makes the path to a **real BlueROV2 over MAVLink/BlueOS with a
physical CT probe** a backend swap, not a rewrite. The step-by-step plan
(MAVLink backend, BlueOS CT extension, ArduSub SITL HIL, tank test with a
salt gradient, harbour trial) is in [docs/sim_to_real.md](docs/sim_to_real.md).

## Documentation

- [docs/architecture.md](docs/architecture.md) — module map, data flow, how to extend
- [docs/assumptions.md](docs/assumptions.md) — every approximation: what, why, impact
- [docs/holoocean_notes.md](docs/holoocean_notes.md) — verified HoloOcean 2.3.0 API facts
- [docs/sim_to_real.md](docs/sim_to_real.md) — roadmap to the real vehicle

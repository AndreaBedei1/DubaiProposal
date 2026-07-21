# Proposal Phase-1 checklist — promise → implementation → evidence

Maps every commitment in the proposal's **Phase 1 — by submission
(simulation-complete)** (`BrineWatch_Proposal.tex`, §Roadmap, and the
Locate→Sense→Adapt→Reconstruct→Act mission concept) to where it is implemented
and the evidence that verifies it. All 142 engine-free tests pass
(`python -m pytest tests -q`).

## Simulation platform

| proposal promise | implementation | evidence |
|---|---|---|
| Full-mission demonstration in **HoloOcean 2.x (UE 5.3)** | official 2.3.0 backend + a custom fork with runtime octree rebuild | `brinewatch/simulation/holoocean_backend.py`, `simulation/custom_engine.py`; `outputs/custom_holoocean_mission/run1/` |
| Official **BlueROV2** model | BlueROV2 agent, `control_scheme=1` PID | `simulation/holoocean_backend.py` (`build_scenario`) |
| **Ray-cast sonar** | ImagingSonar (512×256, 1–40 m, 120°×20°) | `sensors/sonar_types.py`; recorded frames in `outputs/localization/v2_run1/` |
| **Configurable currents** | environment current dir/speed + idealized tide | `configs/benchmark_dynamic.yaml`; dynamic benchmark `outputs/experiments/dynamic_validation/` |
| **Analytic plume** — negatively-buoyant jet + seabed gravity current (Roberts-type), tide-advected | `BrinePlume` (near-field Gaussian + far-field bottom gravity current), 3-D `salinity(x,y,z,t)` | `brinewatch/plume/model.py`; `tests/test_plume*.py` |
| **Virtual CT sensor** with realistic noise | `VirtualCTD` sampling at the vehicle pose | `brinewatch/sensors/ctd.py`; `tests/test_ctd.py` |
| **Deliberately declared analytic plume** | stated in every report/README/movie end-card | footers throughout; `docs/assumptions.md`, `LIMITATIONS.md` |

## Mission loop (Locate → Sense → Adapt → Reconstruct → Act)

| proposal step | implementation | evidence |
|---|---|---|
| **Locate** — sonar finds the pipe/diffuser, anchors the survey frame; never receives the true position | background-subtraction + in-situ **diffuser-line** localizer; chart prior only | LOCATE **1.65 m** in `outputs/custom_holoocean_mission/run1/locate_result.json`; `CUSTOM_LOCALIZATION_STUDY.md`; `tests/test_insitu_locator.py` |
| **Sense** — continuous S/T/depth along baseline transects | `MissionRunner` BASELINE crossing transects + continuous CTD | `brinewatch/mission/runner.py`; `samples.csv` per run |
| **Adapt** — online GP, next waypoints by expected information gain, follow the boundary | `AdaptivePlanner` on the anisotropic GP | `brinewatch/planning/adaptive.py`, `mapping/gp_mapper.py`; benchmark below |
| **Reconstruct** — 3-D isohaline map with explicit uncertainty | 3-D volumetric GP → slices + iso-surface + volume + GP std | `brinewatch/mapping/volumetric.py`; `outputs/volumetric/`; `tests/test_volumetric.py` |
| **Act** — automatic compliance verdict; living digital twin (trends, alerts) | three-state screening + self-contained dashboard + site-history ledger | `evaluation/screening.py`; `outputs/dashboard/index.html`; `site_history/` |

## The three named Phase-1 deliverables

| deliverable | status | evidence |
|---|---|---|
| **Mission video** | ✔ | `outputs/video_demo/mission_movie/mission_movie.mp4` (~28 s, assembled from real mission outputs; `make_mission_movie.py`) |
| **Lawnmower-vs-adaptive benchmark at equal battery** | ✔ | `outputs/experiments/{static,dynamic}_validation/` — 12 held-out seeds, equal 1600 m budget, full metric set (RMSE/MAE/F1/IoU/coverage/useful-sample-fraction/verdict); `run_benchmark.py` |
| **Dashboard with automatic compliance verdict** | ✔ | `outputs/dashboard/index.html` — latest CLEAR/REVIEW/EXCEEDANCE banner, per-mission maps, site trends; `build_dashboard.py` |

## Delivered beyond the Phase-1 proposal

- **The actual spawned outfall is sonar-visible** via the custom fork's runtime
  octree rebuild (the official octree is static → spawned props are invisible;
  proven bit-identical). `SONAR_VALIDATION.md`, `outputs/sonar_truth/`.
- **Collision-safe navigation** — a hazard field (from the sonar estimate +
  chart) keeps a standoff and routes over/around the structure: **0 collisions**
  in-engine. `brinewatch/planning/safe_nav.py`; `tests/test_safe_nav*.py`.
- **In-situ (no-baseline) localization** with bootstrap uncertainty, compared to
  background subtraction under a clutter sweep. `outputs/localization/compare/`.

## Honest limitations (unchanged from the proposal's declarations)

The plume is an analytic surrogate (not CFD); water properties are virtual;
screening is not regulatory certification; sonar detector thresholds are tuned
on simulated acoustics; no field data exists yet. Full ledger:
`docs/assumptions.md`, `docs/application/pfh2026/LIMITATIONS.md`. The adaptive
benefit is a **sample-efficiency** result (better boundary-F1 at low budget),
not a universal error reduction — see `outputs/experiments/README.md`.

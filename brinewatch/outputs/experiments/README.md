# Final experiments — consolidated results (Phase 6)

All experiments below use a **held-out validation** seed set (seeds 100–111),
separate from the development seeds (0–4) used to tune planners, gates and the
screening policy. The plume is the documented analytic **simulation surrogate**;
reconstruction error is scored against it for evaluation only.

## 1. Adaptive vs lawnmower, equal budget (kinematic, 12 validation seeds)

Every planner runs the identical LOCATE + BASELINE, then differs only in the
SURVEY phase at the SAME 1600 m travel budget. Metrics at full budget
(mean ± std over 12 seeds); see `static_validation/` and `dynamic_validation/`.

**Static plume:**

| planner | RMSE (plume) | MAE | boundary F1 | boundary IoU | coverage | useful-sample frac | verdict acc |
|---------|---:|---:|---:|---:|---:|---:|---:|
| adaptive  | 0.484 ± 0.086 | 0.301 | 0.733 ± 0.069 | 0.584 | **0.909** | **0.281** | 0.67 |
| lawnmower | **0.361 ± 0.069** | 0.286 | **0.801 ± 0.049** | **0.671** | 0.799 | 0.220 | **0.83** |

**Dynamic plume (tidal reversal / current):**

| planner | RMSE (plume) | MAE | boundary F1 | boundary IoU | coverage | useful-sample frac | verdict acc |
|---------|---:|---:|---:|---:|---:|---:|---:|
| adaptive  | 0.543 ± 0.125 | 0.358 | 0.728 ± 0.079 | 0.579 | **0.898** | **0.297** | 0.67 |
| lawnmower | **0.359 ± 0.066** | 0.295 | **0.785 ± 0.039** | **0.647** | 0.799 | 0.220 | 0.67 |

**Honest reading (this is not "adaptive wins everything"):**

- Adaptive concentrates samples **inside the plume** — higher useful-sample
  fraction (0.28–0.30 vs 0.22) and higher plume coverage. In the learning
  curves (`learning_curves.png`) this makes it reach a good **boundary F1 at
  lower budget** (≈ 0.71 at 800 m vs lawnmower ≈ 0.62): it delineates the plume
  faster, the operationally relevant regime for a costly ROV.
- At **full** budget the lawnmower's uniform coverage reconstructs the whole
  field better (lower RMSE, higher F1/IoU) and, on the static case, gives higher
  verdict accuracy. The confidence bands overlap, so the differences are modest.
- Take-away: adaptive is a **sample-efficiency** play (find and bound the plume
  under budget pressure), not a universally lower-error map. Reported as such.

## 2. Sonar localization: in-situ vs background subtraction

See `../localization/compare/`. Both modes on the same recorded engine frames:
background subtraction is best on clean data (2.3 m) but degrades to 10.8 m
under unmodelled clutter; the in-situ single-mission mode needs no baseline,
stays 2–6 m under clutter, and is the only mode reporting an uncertainty. In the
in-engine mission (§4) the in-situ diffuser-line fit rejects an off-axis scene
rock the plain consensus locked onto (25 m → 1.65 m).

## 3. Volumetric (multi-altitude 3-D) reconstruction

See `../volumetric/`. Three altitude bands → one 3-D GP → terrain-following
x-y-z reconstruction: plume volume 5477 m³ (truth 3756), RMSE 2.31 PSU, volume
IoU 0.40; slices + iso-surface figures.

## 4. Custom-HoloOcean end-to-end mission, collision-safe

See `../custom_holoocean_mission/run1/`. Motion + sensing in the fork engine:
sonar LOCATE 1.65 m, 271 in-engine CTD samples, **0 collisions**, 2 detours,
**min structure clearance 3.49 m** (standoff 2.0 m), screening REVIEW.
Collisions and completion are the real engine flags; the survey completed within
budget.

## 5. Repeated-mission digital-twin history

See `../../site_history/` and the dashboard (`../dashboard/index.html`). A
labelled-simulated campaign of repeated missions over one site with the plant
ramping discharge: the ledger tracks max anomaly, worst-case exceedance
probability, exceedance area and the three-state verdict per mission; the
dashboard renders the longitudinal trends.

## Metric checklist (Phase 6)

| requested metric | where |
|---|---|
| RMSE / MAE | §1 tables (rmse_plume, rmse_all, mae_all in records) |
| boundary F1 / IoU | §1 tables |
| coverage | §1 tables (coverage_frac) |
| useful-sample fraction | §1 tables (in_plume_frac) |
| localization error | §2, §4 |
| collisions | §4 (0) |
| completion rate / budget usage | §1 (equal budget), §4 (220/220 m) |
| screening correctness | §1 (verdict acc), records `screening_outcome` |
| uncertainty calibration | §1 records `max_std_outside_psu`; §2 in-situ σ vs error |
| dynamic plume / current | §1 dynamic table |
| repeated-mission history | §5 |
| calibration vs validation split | dev seeds 0–4 vs validation seeds 100–111 (this file) |

Reproduce the benchmarks:

```bash
python scripts/run_benchmark.py --config configs/benchmark_static.yaml  --seed-start 100 --seeds 12
python scripts/run_benchmark.py --config configs/benchmark_dynamic.yaml --seed-start 100 --seeds 12
```

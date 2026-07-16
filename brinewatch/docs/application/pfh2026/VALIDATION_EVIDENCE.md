# Validation evidence — claim → proof mapping

Every application-facing claim is listed with its evidence. Paths are
relative to `brinewatch/`. Where evidence is partial, the claim is scoped
accordingly (and phrased identically in all documents).

| # | Claim | Evidence | Scope notes |
|---|---|---|---|
| 1 | The mission stack runs end-to-end in official, unmodified HoloOcean 2.3.0 (BlueROV2, PierHarbor) | `outputs/brinewatch_pfh2026_*/` (mission_log.jsonl, report.html, plume_maps.npz); `docs/application/pfh2026/environment_manifest.md` | multiple full missions; wall time ~19 min for 1100 m at 1 Hz sonar |
| 2 | Adaptive sampling beats a lawnmower under scarce budget | `assets/results/benchmark_records_static.csv` (20 held-out seeds/planner), `learning_curves_static.png`, BENCHMARK_REPORT.md | RMSE −11–15 %, boundary F1 +17 % at 25–50 % budget; lawnmower wins at full coverage (stated) |
| 3 | Three-state screening never produced a wrong conclusive result | same records: `screening_outcome` column — 0 "wrong" in 320 evaluations (2 families × 2 planners × 20 seeds × 4 checkpoints) | REVIEW = honest inconclusive, counted separately |
| 4 | The official sonar sees stock structures; runtime props are acoustically invisible | `assets/sonar/gate/` (bit-identical present/absent frames, z=0.00); `assets/sonar/pier_sonar_aimed.png` vs `pier_sonar_openwater_control.png` | the central documented limitation + fallback |
| 5 | The detector finds the structure in real frames and stays silent in open water | `tests/fixtures/pier_sonar_*.npz` + `tests/test_sonar_stack.py` (green); cross-pose world agreement < 1 m on clean frames | clean-frame result |
| 6 | Under mission noise, single-ping gates fail; persistence-based localization is required | `assets/sonar/detector_eval.png/json` (538 recorded frames: strength distributions overlap); SONAR_VALIDATION.md §4–5 | measured, drove the localizer design |
| 7 | Sonar-based LOCATE runs with zero ground-truth access | `brinewatch/perception/sonar_localizer.py` (constructor takes no truth; leakage audit), `mission/runner.py` (config chart prior; evaluator-only GT), demo run summary `sonar` block | fallback to prior is loudly flagged and disqualifies the run as sonar evidence |
| 8 | Localization error of the official demo | `outputs/brinewatch_pfh2026_<final>/summary.json` → `localization_error_m` `[FILL FROM FINAL RUN]` | in a structure-rich harbor the locator resolves the structure complex nearest the chart prior |
| 9 | Terrain-calibrated scene placement works on real uneven terrain | live logs: robust plane RMSE 0.06–0.12 m vs 4.6 m unrobust (poisoned by structure soundings); `scene_manifest.json` per run | failure mode measured, fix verified live |
| 10 | Longitudinal screening tracks a discharge trend | `assets/results/site_history_trend.png` + `site_history_ledger.jsonl` (6 simulated missions: CLEAR×2 → REVIEW → POSSIBLE_EXCEEDANCE×3) | clearly labelled simulated campaign |
| 11 | The architecture transfers to the physical ROV | `brinewatch/simulation/base.py` (backend abstraction), `docs/sim_to_real.md` (MAVLink plan), PHYSICAL_VALIDATION_PROTOCOL.md | plan + owned hardware; no physical test executed yet |
| 12 | Reproducibility | README one-command demos; **111 passed** engine-free tests (`python -m pytest -q`, 2026-07-17, Python 3.9.25; engine tests carry the `holoocean_integration` marker and are excluded by default); GitHub Actions CI runs the same suite; configs versioned; environment manifest | HoloOcean install documented as prerequisite for engine runs |

Claims explicitly NOT made: regulatory certification; field validation;
first-ever robotic brine mapping; commercial cost figures; unattended
operation readiness.

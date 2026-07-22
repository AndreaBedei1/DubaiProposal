# BrineWatch final technical results

All performance values are simulation results. The salinity field is an analytic surrogate, not CFD or field truth. The planned localisation sensor is the Omniscan 450 FS forward-looking imaging sonar.

## Evidence ledger

| Evidence | Backend / scenario | What it supports | What it does not support |
|---|---|---|---|
| Isolated custom-HoloOcean mission | Native vehicle motion, native imaging sonar, analytic salinity sampled along the engine trajectory | Integration, localisation, navigation, sensing and safety | Headline plume-reconstruction performance |
| Flagship 2-D result | Demo-optimised high-contrast analytic surrogate | Clear workflow demonstration and reconstruction metrics | Field accuracy or CFD validation |
| Equal-evidence comparison | Same surrogate, area, noise, 48 readings and 300 m cap | Relative sampling efficiency within the stated benchmark | Universal superiority in every site or condition |
| Volumetric result | One anisotropic 3-D GP over four altitude bands | Coherent 3-D reconstruction and visible uncertainty | Measured environmental volume |

## Isolated in-engine mission

- Instance: `bwp26-fa3`; private runtime root: `C:\bwrt\bwp26-fa3`.
- Private instance ID, IPC namespace, octree cache, temp/cache directories, logs and outputs.
- Process inventory before and after the run was empty; only launcher-owned PID 42008 was closed; `other_processes_terminated` is empty.
- 564 simulated CT samples; 394.85 m travelled; zero collisions; four safe detours.
- Minimum measured clearance 1.85 m against a 2.0 m target. The 0.15 m undershoot is disclosed.
- Screening: REVIEW against non-compliant surrogate truth.
- Reconstruction: 2.720 PSU RMSE, 0.000 boundary F1, 0.000 boundary IoU. This weak science result is deliberately retained as stress evidence and is not the competition headline.

The cinematic run used a second fully isolated instance, `bwp26-cin1`, with its own 1920 × 1080 engine session. Neither manifest records any external process termination.

## Sonar localisation

The flagship localisation uses recorded custom-HoloOcean imaging-sonar frames, two independent search radii and inverse-uncertainty consensus.

- Centre error: **2.353 m**.
- Posterior uncertainty radius: **1.669 m**.
- Confirmation spread: **4.771 m**, below the 5.0 m acceptance limit.
- Prior robustness: **5/5 valid non-fallback fits**; median scored error 4.243 m.
- Oracle input: none. Silent fallback: none. Truth is used only after estimation for scoring.

## Flagship high-contrast 2-D demonstration

Configuration: `brinewatch/configs/pfh2026_flagship_demo.yaml`.

- 591 samples; 516.55 / 520 m mission budget.
- Plume RMSE: **0.3415 PSU**.
- Boundary F1: **0.947**.
- Boundary IoU: **0.900**.
- Relevant-region coverage: **0.770**.
- Screening: **POSSIBLE EXCEEDANCE**, correct and conclusive against non-compliant surrogate truth.
- Maximum reconstructed exceedance: +1.234 PSU; maximum exceedance probability: 1.00.

This scenario intentionally increases plume contrast and is documented as demo-optimised. It preserves the accepted outfall geometry and the Locate → Sense → Adapt → Reconstruct → Act workflow.

## Three-state screening examples

| Case | Surrogate truth | Output | Samples | Key evidence |
|---|---:|---:|---:|---|
| Compliant reference | PASS | CLEAR | 1,049 | Correct; P(exceed) 0.036; 0.0487 PSU RMSE; boundary F1 1.000 |
| Borderline uncertainty | PASS | REVIEW | 290 | Inconclusive by design; P(exceed) 0.363; 0.5749 PSU RMSE |
| Flagship non-compliant | FAIL | POSSIBLE EXCEEDANCE | 591 | Correct; P(exceed) 1.000; 0.3415 PSU RMSE |

## Equal-evidence comparison

Eight seeds per method; 24 runs total. Each method receives 48 readings, the same 300 m travel cap, area, plume truth and 0.03 PSU sensor noise. The sparse design uses 24 fixed stations with a second reading at each station. Time estimates assume 0.6 m/s vehicle speed, 45 s fixed-station dwell and 2 s rolling-ROV reading overhead.

| Metric, mean over 8 seeds | Sparse fixed | Regular survey | BrineWatch adaptive |
|---|---:|---:|---:|
| Plume RMSE, PSU ↓ | 1.151 | 1.661 | **0.758** |
| Boundary F1 ↑ | 0.000 | 0.287 | **0.789** |
| Boundary IoU ↑ | 0.000 | 0.177 | **0.656** |
| Missed-plume fraction ↓ | 1.000 | 0.817 | **0.284** |
| Useful-sample fraction ↑ | 0.167 | 0.229 | **0.701** |
| Mean posterior std, PSU ↓ | **2.169** | 2.359 | 2.292 |
| Travel distance, m | 297.8 | 300.0 | 297.5 |
| Indicative operating time, min | 44.27 | 9.93 | 9.86 |

Screening outcomes:

| Method | CLEAR | POSSIBLE EXCEEDANCE | REVIEW | Conclusive | Accuracy when conclusive | False CLEAR | False exceedance | REVIEW rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Sparse fixed | 0/8, 0% | 0/8, 0% | 8/8, 100% | 0% | n/a | 0 | 0 | 100% |
| Regular survey | 0/8, 0% | 4/8, 50% | 4/8, 50% | 50% | 100% | 0 | 0 | 50% |
| BrineWatch adaptive | 0/8, 0% | 8/8, 100% | 0/8, 0% | 100% | 100% | 0 | 0 | 0% |
| All methods | 0/24, 0% | 12/24, 50% | 12/24, 50% | 50% | 100% | 0 | 0 | 50% |

The empirical false-CLEAR count, used here as the probability-of-missing-an-exceedance indicator, is zero for all methods. This is not equivalent to useful detection: sparse fixed sampling abstains in every run and misses the reconstructed plume boundary. The REVIEW rate is therefore reported alongside false-CLEAR counts.

## Volumetric mission

Configuration: `brinewatch/configs/pfh2026_flagship_volumetric.yaml`.

- Four altitude bands: 0.8, 1.6, 2.8 and 4.5 m above bed.
- 912 samples update one coherent anisotropic 3-D Gaussian process.
- 3-D RMSE: **0.477 PSU**; MAE: **0.238 PSU**.
- Volume IoU: **0.805**.
- Reconstructed threshold volume: **2,051.3 m³** versus **2,448.2 m³** surrogate truth: 16.2% underestimation.
- The visual shows trajectory, altitude bands, reconstructed surface, confident core and possible uncertainty bound.

## Feasibility and cost assumptions

- Full new-build planning range: **USD 21.5k–44k**.
- Incremental next step with the already-owned BlueROV2 and Omniscan 450 FS: **USD 9k–22.5k**.
- Indicative day ranges including targeted reference sampling: shore **USD 3.4k–8.9k**; small boat **USD 4.9k–13.4k**; sparse manual **USD 5k–12k**; spatial vessel survey **USD 8k–22k**.
- Midpoint break-even illustration: approximately **2–7 repeated missions**, not a guaranteed saving.
- Assumptions: two operators, 2.5–4 h on water, 4–8 h reporting, 12 missions/year and five-year amortisation.

Cost ranges are transparent planning assumptions, not quotations. If vessel, permit and accredited-sampling requirements remain unchanged, the benefit is better spatial evidence rather than lower cost.

## Claims boundary

Supported: simulation-led prototype feasibility; collision-free isolated in-engine demonstration; uncertainty-aware screening; relative adaptive-sampling performance in the stated benchmark; repeatable digital-twin concept; indicative planning economics.

Not supported: regulatory certification; field accuracy; CFD validation; guaranteed savings; universal replacement of accredited monitoring; autonomous unsupervised deployment.


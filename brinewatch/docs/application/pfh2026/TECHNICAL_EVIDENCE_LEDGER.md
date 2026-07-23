# BrineWatch PFH 2026 technical evidence ledger

Status: **Initial Prototype or Model**  
Evidence freeze: 22 July 2026

This ledger contains the metrics, assumptions and limitations intentionally removed from the public competition report. All performance values are simulation results. The plume is an analytic simulation surrogate, not CFD or field truth. The planned sonar is the Omniscan 450 FS forward-looking imaging sonar.

## 1. Evidence classes

| Evidence | Backend / scenario | Supported interpretation | Unsupported interpretation |
|---|---|---|---|
| Isolated custom-HoloOcean mission | Native vehicle motion and imaging sonar; analytic salinity sampled along the engine trajectory | Integration, localisation, navigation, sensing and safety | Headline plume reconstruction |
| Flagship 2-D result | Demo-optimised high-contrast analytic surrogate | Clear workflow demonstration and reconstruction metrics | Field accuracy or CFD validation |
| Equal-evidence comparison | Same surrogate, area, noise, 48 readings and 300 m cap | Relative sampling efficiency in the stated benchmark | Universal superiority |
| Volumetric result | One anisotropic 3-D GP, four altitude bands | Coherent 3-D reconstruction and visible uncertainty | Measured environmental volume |

## 2. Isolation and custom-HoloOcean mission

- Mission instance: `bwp26-fa3`; runtime root: `C:\bwrt\bwp26-fa3`.
- Cinematic instance: `bwp26-cin1`; runtime root: `C:\bwrt\bwp26-cin1`.
- Each run used private shared memory, semaphore names, instance ID, octree cache, Unreal cache, temp directory, logs and outputs.
- Both manifests record empty matching-process inventories before and after execution, `engine_owned_by_launcher: true` and an empty `other_processes_terminated` list.
- The launcher closed only its recorded Unreal PID. No global process-name termination was used.

Custom mission evidence:

- 564 simulated CT samples; 394.85 m travelled; 400 m budget.
- Zero collisions; four safe detours.
- Minimum measured clearance 1.85 m against a 2.0 m target. The 0.15 m undershoot is disclosed.
- Screening: REVIEW against non-compliant surrogate truth.
- Reconstruction: 2.7203 PSU RMSE; boundary F1 0.000; boundary IoU 0.000; coverage 0.673; useful-sample fraction 0.238.
- Interpretation: strong vehicle, native-sonar and safety evidence; weak plume reconstruction. It is not the scientific headline.

## 3. Sonar localisation

- Source: recorded custom-HoloOcean imaging-sonar frames.
- Two independent search radii with inverse-uncertainty consensus.
- Centre error: 2.353 m.
- Posterior uncertainty radius: 1.669 m.
- Confirmation spread: 4.771 m; acceptance limit: 5.0 m.
- Prior robustness: 5/5 valid non-fallback fits; median scored error 4.243 m.
- Oracle input: none. Silent fallback: none.
- Truth was used only after estimation for scoring.

## 4. Flagship and three-state screening

Flagship configuration: `brinewatch/configs/pfh2026_flagship_demo.yaml`.

- Demo-optimised high-contrast analytic surrogate; accepted outfall geometry unchanged.
- 591 samples; 516.55 / 520 m mission budget.
- Plume RMSE 0.3415 PSU; boundary F1 0.947; boundary IoU 0.900; relevant-region coverage 0.770.
- Output: POSSIBLE EXCEEDANCE; correct and conclusive against non-compliant surrogate truth.
- Maximum reconstructed exceedance +1.234 PSU; maximum exceedance probability 1.000.

| Screening case | Surrogate truth | Output | Samples | P(exceed) | RMSE | Boundary F1 |
|---|---:|---:|---:|---:|---:|---:|
| Compliant reference | PASS | CLEAR | 1,049 | 0.036 | 0.0487 PSU | 1.000 |
| Borderline uncertainty | PASS | REVIEW | 290 | 0.363 | 0.5749 PSU | 0.783 |
| Flagship non-compliant | FAIL | POSSIBLE EXCEEDANCE | 591 | 1.000 | 0.3415 PSU | 0.947 |

## 5. Equal-evidence comparison

Eight seeds per method; 24 runs total. Each method receives 48 readings, the same 300 m travel cap, survey area, analytic plume truth and 0.03 PSU sensor noise. Sparse sampling uses 24 fixed stations with one replicate per station. Time estimates assume 0.6 m/s vehicle speed, 45 s fixed-station dwell and 2 s rolling-ROV reading overhead.

| Metric, mean over eight seeds | Sparse fixed | Regular survey | BrineWatch adaptive |
|---|---:|---:|---:|
| Plume RMSE, PSU | 1.151 | 1.661 | 0.758 |
| Boundary F1 | 0.000 | 0.287 | 0.789 |
| Boundary IoU | 0.000 | 0.177 | 0.656 |
| Missed-plume fraction | 1.000 | 0.817 | 0.284 |
| Useful-sample fraction | 0.167 | 0.229 | 0.701 |
| Mean posterior std, PSU | 2.169 | 2.359 | 2.292 |
| Maximum outside std, PSU | 2.877 | 4.500 | 4.496 |
| Travel distance, m | 297.8 | 300.0 | 297.5 |
| Indicative operating time, min | 44.27 | 9.93 | 9.86 |

| Method | CLEAR | POSSIBLE EXCEEDANCE | REVIEW | Conclusive rate | Accuracy if conclusive | False CLEAR | False exceedance |
|---|---:|---:|---:|---:|---:|---:|---:|
| Sparse fixed | 0/8 | 0/8 | 8/8 | 0% | n/a | 0 | 0 |
| Regular survey | 0/8 | 4/8 | 4/8 | 50% | 100% | 0 | 0 |
| BrineWatch adaptive | 0/8 | 8/8 | 0/8 | 100% | 100% | 0 | 0 |
| All methods | 0/24 | 12/24 | 12/24 | 50% | 100% | 0 | 0 |

The false-CLEAR count is zero for all methods, but sparse sampling abstains in every run and misses the reconstructed plume boundary. REVIEW rate and missed-plume fraction must therefore remain visible beside false-CLEAR counts.

## 6. Volumetric mission

Configuration: `brinewatch/configs/pfh2026_flagship_volumetric.yaml`.

- Four altitude bands: 0.8, 1.6, 2.8 and 4.5 m above bed.
- Samples per band: 228, 227, 226 and 231; 912 total.
- One coherent anisotropic 3-D Gaussian process.
- RMSE 0.477 PSU; MAE 0.238 PSU; volume IoU 0.805.
- Reconstructed threshold volume 2,051.3 m3; surrogate truth 2,448.2 m3; 16.2% underestimation.
- Reconstructed bottom area 651.8 m2; surrogate truth 1,042.9 m2.
- Mean reconstructed plume altitude 2.86 m; surrogate truth 2.53 m.
- Estimated peak 65.231 PSU; surrogate peak 65.272 PSU.
- Uncertain volume 24,351.4 m3 and mean standard deviation inside the reconstructed plume 1.551 PSU. These values show that uncertainty remains substantial and should not be hidden.

## 7. Feasibility and costs

- Full new-build planning range: USD 21.5k-44k.
- Incremental next-step range with owned BlueROV2 and Omniscan 450 FS: USD 9k-22.5k.
- Indicative survey day including targeted reference sampling: shore USD 3.4k-8.9k; small boat USD 4.9k-13.4k.
- Comparison planning ranges: sparse manual USD 5k-12k; spatial vessel survey USD 8k-22k.
- Midpoint break-even illustration: approximately 2-7 repeated missions; not a guaranteed saving.
- Assumptions: two operators; 2.5-4 h on water; 4-8 h reporting; 12 missions/year; five-year equipment amortisation.
- Public verification anchors: BlueROV2 starting at USD 4,900 and Omniscan 450 FS starting at USD 2,490 at the time of the 22 July 2026 review. CT payload, integration, labour, vessel and permit costs require current quotations.

If vessel, permits and accredited sampling remain unchanged, the economic benefit may disappear. The remaining value is more informative spatial evidence, combined infrastructure inspection and screening, and a repeatable digital site history.

## 8. Video disclosure

- Main public video uses 625 consecutive 1920x1080 custom-HoloOcean RGB frames for the 20.8-second approach and inspection segment.
- The dedicated cinematic camera path is genuine to the simulated scene but is not a telemetry-synchronised replay of the scientific mission.
- Scientific result images are fixed in frame with no pan/zoom transformation.
- The progressive 3-D segment is generated from the validated volumetric result.
- Grading disclosure: the continuous engine footage carries a stylistic underwater grade (highlight compression of the strong surface light, cool colour cast, a vertical depth-fog overlay denser towards the surface, restrained sharpening and a gentle vignette). The grade changes look only; scene content, geometry and camera path are unchanged. Scientific result images are never graded.

## 9. Claims boundary

Supported claims:

- simulation-led prototype feasibility;
- isolated collision-free custom-HoloOcean integration demonstration;
- forward-looking imaging-sonar localisation without oracle input;
- uncertainty-aware three-state screening;
- relative adaptive-sampling performance within the stated benchmark;
- coherent 2-D and 3-D surrogate reconstructions;
- repeatable digital-twin concept;
- indicative economic planning ranges.

Claims that must not be made:

- regulatory certification or autonomous compliance determination;
- field accuracy or CFD validation;
- guaranteed cost savings or guaranteed break-even;
- universal replacement of accredited monitoring;
- unsupervised field deployment readiness;
- measured environmental plume volume.

## 10. Next validation gate

Integrate a calibrated conductivity-temperature payload, establish traceable timing and calibration, validate against known gradients in controlled water and then run a supervised nearshore pilot with independent reference samples.

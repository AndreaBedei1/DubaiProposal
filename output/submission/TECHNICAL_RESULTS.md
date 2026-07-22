# BrineWatch - approved competition numbers

Use the first table for headlines. Keep the qualification in the last column when presenting the number.

| Result | Value | Qualification |
|---|---:|---|
| Sonar localization centre error | 1.65 m | custom HoloOcean, native simulated sonar, no ground-truth input to localizer |
| In-engine survey | 220 m / 271 samples | analytic plume surrogate sampled along a real engine trajectory |
| Safety | 0 collisions / 3.49 m minimum clearance | two automatic safe detours |
| Mission map | 2.45 PSU plume RMSE / 0.686 boundary F1 | single flagship custom-engine mission |
| Screening | REVIEW vs ground-truth PASS | conservative and inconclusive, not counted as correct |
| 3-D reconstruction | 1,770 samples / three altitudes | simulation-based surrogate, not CFD or field truth |
| 3-D quality | 2.31 PSU RMSE / 0.399 volume IoU | estimated plume volume is 5,477 m3 vs 3,756 m3 truth |
| Dynamic benchmark at 50% budget | 18.7% lower plume RMSE / 14.2% higher relative boundary F1 | adaptive vs lawnmower, 12 held-out seeds |
| Screening benchmark | 0 wrong conclusive outputs in 192 evaluations | REVIEW is inconclusive, not correct |

## Honest stress result

An isolated extended 360 m mission completed 448 samples with zero collisions and 3.02 m minimum clearance, demonstrating navigation endurance. It did **not** improve the science result: localization error increased to 3.38 m and the screening verdict was wrong. This run is not used as headline evidence. It motivates multi-pass localization, stronger calibration and a stricter abstention policy.

## Claims not to make

- Do not call the current system field validated.
- Do not call the analytic plume surrogate CFD.
- Do not describe REVIEW as a correct decision.
- Do not say adaptive sampling is always better. The lawnmower route is stronger at full dense coverage in the current benchmark.
- Do not describe the final video as a continuous telemetry-synchronised replay. It is a cinematic edit of genuine simulator captures and recorded result panels.
- Do not claim regulatory compliance or replacement of accredited sampling.

## Cost story

- Complete new-build planning range: USD 13,550-31,440.
- Incremental next gate, with owned BlueROV2 and Omniscan retained: approximately USD 3,000-10,000.
- These are planning ranges, not supplier quotations; taxes, shipping, certification, permits and longer campaigns are excluded.

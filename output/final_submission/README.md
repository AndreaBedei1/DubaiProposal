# BrineWatch — final competition package

Status: **Initial Prototype or Model**  
Package date: 22 July 2026

## Upload these files

- **Report:** `BrineWatch_PFH2026_Report.pdf` — 13 pages, 2.7 MB. This is the primary PDF to upload.
- **Main video:** `BrineWatch_PFH2026_Final_1080p.mp4` — 1920 × 1080, 30 fps, 51.0 s. This is the video to publish or link in the application.
- **Optional short cut:** `BrineWatch_PFH2026_Short_1080p.mp4` — 1920 × 1080, 30 fps, 34.0 s.
- **Lead image:** `hero_structure.png`.

The main video opens with 20.8 seconds / 625 consecutive RGB frames captured in the real custom-HoloOcean scene. The dedicated cinematic camera follows a smooth path and is not presented as a telemetry-synchronised replay. The outfall is visible from the first second. A separate eight-second sequence progressively reveals the 3-D samples, altitude bands, trajectory, Gaussian-process volume and uncertainty.

## Best presentation assets

- `sonar_localization.png` — Omniscan 450 FS forward-looking imaging-sonar concept and multi-radius confirmation.
- `mission_reconstruction.png` — flagship 2-D truth, reconstruction, boundary and uncertainty.
- `plume_3d.png` — four altitude bands, trajectory, reconstructed plume and confidence bounds.
- `digital_twin_dashboard.png` — latest site map, uncertainty, verdict, history and recommended action.
- `benchmark_comparison.png` — equal-evidence comparison with sparse fixed stations and a regular survey.

## Headline numbers to use

- **Real custom-HoloOcean mission:** 395 m travelled, 564 simulated CT readings, zero collisions, minimum measured structure clearance 1.85 m. Use this as vehicle, native-sonar and safety evidence.
- **Sonar localisation:** 2.35 m centre error, 1.67 m uncertainty radius, two search radii confirmed, 5/5 non-fallback prior-perturbation fits. Truth was used only after estimation for scoring.
- **Flagship 2-D demo:** 0.342 PSU plume RMSE, 0.947 boundary F1, 0.900 boundary IoU, correct conclusive **POSSIBLE EXCEEDANCE**.
- **Equal-evidence benchmark:** eight seeds, 48 readings and a 300 m cap per method. Adaptive RMSE 0.758 PSU and IoU 0.656, versus 1.661 / 0.177 for the regular survey and 1.151 / 0.000 for sparse fixed stations. Adaptive was conclusive and correct in 8/8 runs; the regular survey was conclusive in 4/8; sparse fixed stations returned REVIEW in 8/8.
- **3-D demo:** 0.477 PSU RMSE, 0.805 volume IoU, 2,051 m³ reconstructed versus 2,448 m³ surrogate truth (16.2% underestimation).

All values above are simulation results. The flagship is an explicitly labelled, demo-optimised high-contrast analytic plume surrogate; it is not CFD or field truth.

## What not to emphasise

- Do not headline the 912 volumetric samples without the RMSE and volume IoU.
- Do not use the custom-HoloOcean reconstruction as the scientific result: that difficult run returned REVIEW and had 2.72 PSU RMSE and zero boundary F1/IoU. It is retained as honest vehicle/sensor/safety evidence.
- Do not present plume volume as measured environmental truth.
- Do not claim regulatory certification, CFD validation, guaranteed cost savings or universal replacement of accredited monitoring.
- Do not describe the imaging-sonar concept using another sonar class. The planned sensor is the **Omniscan 450 FS forward-looking imaging sonar**.

## Supported claim

> BrineWatch provides more informative spatial evidence under constrained survey time and helps direct certified/manual sampling toward the locations that matter.

The current prototype supports simulation-led feasibility, adaptive-planning and digital-twin claims. The next gate is a calibrated CT payload, controlled-water validation and then a supervised nearshore pilot with independent reference samples.

## Supporting material outside this upload folder

- Video manifest and key frames: `../fasttrack/video/`
- Continuous and progressive-reconstruction source clips: `../fasttrack/video_sources/`
- Isolation manifests: `C:\bwrt\bwp26-fa3\run_manifest.json` and `C:\bwrt\bwp26-cin1\run_manifest.json`
- Full numerical details: `TECHNICAL_RESULTS.md`
- Paste-ready application copy: `SUBMISSION_FIELDS.md`


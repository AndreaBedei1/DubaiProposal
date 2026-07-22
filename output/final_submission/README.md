# BrineWatch - redesigned competition package

Status: **Initial Prototype or Model**  
Package date: 22 July 2026

This directory separates the simple public story from the full technical evidence.

## Upload these files

1. **Primary PDF:** `UPLOAD/BrineWatch_PFH2026_Public_Competition_Report.pdf`
   - 10 pages, 6.8 MB.
   - Rebuilt from zero for technical and non-technical reviewers.
   - The first three pages explain the problem, goal, robot and workflow before introducing metrics.

2. **Primary video:** `UPLOAD/BrineWatch_PFH2026_Public_1080p.mp4`
   - 43.9 seconds, 1920 x 1080, 30 fps, 77.1 MB.
   - H.264 High Profile master at CRF 10, with a compact top-right caption panel.
   - Uses 625 consecutive genuine custom-HoloOcean frames for the continuous approach and inspection.
   - Shows only sonar, one 2-D result, one progressive 3-D result, the digital twin and the next validation step.

3. **Optional short video:** `UPLOAD/BrineWatch_PFH2026_Public_Short_1080p.mp4`
   - 29.7 seconds, 1920 x 1080, 30 fps, 45.1 MB.

Do not upload the technical ledger as the primary project PDF. Use it only if the application allows a supporting technical document.

## Supporting technical evidence

- `TECHNICAL/BrineWatch_PFH2026_Technical_Evidence_Ledger.pdf` - six-page appendix with complete metrics, screening counts, assumptions and claims boundary.
- `TECHNICAL/TECHNICAL_EVIDENCE_LEDGER.md` - searchable source version.
- `TECHNICAL/PUBLIC_VIDEO_MANIFEST.json` - exact scene timings, footage disclosure and fixed-figure motion policy.

## Source scripts

Rebuild copies are included in `SOURCE_SCRIPTS/`:

- `build_public_competition_assets.py`
- `build_public_competition_report.py`
- `build_technical_evidence_appendix.py`
- `make_public_competition_video.py`

The maintained source files remain under `brinewatch/scripts/`.

## Public story in one sentence

> BrineWatch turns one robotic outfall inspection into an uncertainty-aware plume map that directs certified sampling to the locations that matter.

## What the public report communicates

- The problem: isolated measurements can miss the spatial plume boundary.
- The system: BlueROV2, Omniscan 450 FS forward-looking imaging sonar and a planned calibrated conductivity-temperature payload.
- The workflow: Locate -> Sense -> Adapt -> Reconstruct -> Act.
- The twin: an evolving site record containing the latest map, uncertainty, route, sonar location, mission history and recommended next action.
- What works: sonar localisation, collision-free in-engine motion, flagship 2-D reconstruction and coherent 3-D reconstruction.
- What comes next: calibrated CT integration, controlled-water validation and a supervised nearshore pilot.

## Headline evidence

- Sonar localisation: 2.35 m scored centre error; no oracle input.
- Custom-HoloOcean mission: 395 m travelled; 564 simulated CT readings; zero collisions.
- Flagship 2-D reconstruction: 0.900 boundary IoU with a correct conclusive screen.
- Volumetric reconstruction: 0.805 volume IoU across four altitude bands.
- Equal-evidence comparison: 48 readings and a 300 m cap per method; adaptive sampling was conclusive in 8/8 runs, regular survey in 4/8 and sparse fixed sampling in 0/8.

These are simulation results. The flagship plume is an explicitly disclosed demo-optimised analytic surrogate, not CFD or field truth.

## Final quality checks

- Public PDF: all 10 pages rendered and visually inspected at normal laptop scale.
- Technical ledger: all six pages rendered and visually inspected.
- Main video: 1,318 / 1,318 frames decoded; zero black frames.
- Short video: 890 / 890 frames decoded; zero black frames.
- First 10 seconds: all 300 frames checked; high-contrast caption panel remains inside safe margins.
- Sonar, 2-D and digital-twin scenes: fixed frame with cuts/fades only; no pan or zoom.
- Final card: fixed underwater background, high-contrast panel and minimal text.

## Claims boundary

Supported: simulation-led feasibility, isolated in-engine integration, sonar localisation, relative adaptive-sampling performance in the stated benchmark, uncertainty-aware screening and a digital-twin workflow.

Do not claim: regulatory certification, field or CFD validation, guaranteed savings, universal replacement of accredited monitoring or unsupervised field readiness.

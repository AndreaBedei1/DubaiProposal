# Application form fields — ready to paste (PFH 2026)

## Project name

BrineWatch

## Project phase

Initial Prototype or Model

## Project description (~300 words)

Use the text in `PROJECT_DESCRIPTION.md` verbatim.

## Milestones achieved to date (paste-ready condensation)

- End-to-end autonomous survey missions of a BlueROV2 in the official
  HoloOcean marine simulator: sonar-based outfall localization from a chart
  prior (no privileged position information), baseline transects,
  boundary-aware adaptive sampling, Gaussian-process reconstruction with
  uncertainty, and automatic three-state screening against a configurable
  mixing zone.
- Equal-budget planner benchmark on 20 held-out seeds × 2 scenario families:
  adaptive sampling cuts in-plume reconstruction error by 11–15 % and
  improves boundary localization (F1 +17 %) when the travel budget cannot
  densely cover the site; the uncertainty-aware screening produced zero
  wrong conclusive results in 320 evaluations.
- Controlled acoustic-visibility study: on the OFFICIAL simulator
  runtime-spawned props are not in the acoustic octree (documented), but a
  CUSTOM HoloOcean fork rebuilds the octree at runtime so the generated
  outfall IS sonar-visible and is localized by native simulated (non-oracle) sonar with no ground
  truth. Plus an offline detector evaluation harness on recorded sonar
  missions with real-frame test fixtures.
- Automated terrain calibration (range-finder sounding grid + robust plane
  fit), terrain-placed configurable outfall scene, collision recovery and
  survey-safety logic — all exercised in live simulator missions.
- Simulated multi-mission campaign demonstrating longitudinal screening of a
  discharge ramp-up (CLEAR → REVIEW → POSSIBLE EXCEEDANCE), each mission
  producing a self-contained digital report; 86 automated tests, fully
  reproducible from the public repository with standard HoloOcean.
- Physical BlueROV2 and Omniscan SS450 side-scan sonar owned by the team;
  CT-payload retrofit and one-day controlled water-test protocol specified.

## Awards, prizes and featured publications

None to date. (Recommendation: leave the field blank or state "None to
date" — do not list unrelated items.)

## Project video (optional)

Recommended title: "BrineWatch — autonomous brine-plume screening
(simulation prototype)".
Recommended description: "A BlueROV2 localizes a desalination outfall by
sonar, adaptively maps the near-bed salinity plume and issues an
uncertainty-aware screening verdict. All footage is genuine output of the
official HoloOcean simulator; physical trials are the next step.
Code: https://github.com/AndreaBedei1/DubaiProposal"
Public link: [TO ADD if the storyboard video is produced — the field is
optional; do not link placeholder content.]

## Single project PDF

`BrineWatch_PFH2026_Submission_Draft.pdf` (repo root; keep < 20 MB — checked
by scripts/check_pdf_size.py). Compile from
`BrineWatch_PFH2026_Submission_Draft.tex`.

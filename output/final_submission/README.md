# BrineWatch — Prototypes for Humanity 2026 final submission package

Status: **Initial Prototype or Model**
Package date: 22 July 2026

## Upload these files

1. **Primary project PDF (the one to upload in the "Upload Project" form):**
   `UPLOAD/BrineWatch_PFH2026_Final_Project_Proposal.pdf`
   - 12 pages, portrait A4, 3.6 MB (limit: 20 MB).
   - Editorial white/blue design rebuilt from the original proposal's visual language.
   - Structure: cover → problem → monitoring gap → system → mission → digital twin →
     evidence (in-engine mission, 2-D, 3-D) → adaptive benchmark → feasibility + risks →
     costs + roadmap → applications, impact and request → references.
   - Every number is reproduced deterministically from the repository (see
     `proposal_final/README.md`) and matches the technical evidence ledger.

2. **Primary video (link it in the "Project Video" field after uploading to YouTube/Vimeo):**
   `UPLOAD/BrineWatch_PFH2026_Public_1080p.mp4`
   - 43.9 s, 1920x1080, 30 fps, H.264 CRF 10, 61.8 MB.
   - 625 consecutive genuine custom-HoloOcean frames for the approach/inspection,
     then sonar → 2-D map → progressive 3-D → digital twin → closing.
   - Engine footage carries a stylistic underwater grade (sun-glare roll-off, cool cast,
     depth-fog gradient, vignette). Content, geometry and camera path unchanged;
     scientific figures are never graded. Disclosed in the technical ledger, §8.

`UPLOAD/` deliberately contains only these two files — one PDF, one video.
Do not upload the technical ledger as the project PDF; it is a supporting document.

## Supporting technical evidence (keep separate)

- `TECHNICAL/BrineWatch_PFH2026_Technical_Evidence_Ledger.pdf` — complete metrics,
  assumptions, screening counts, claims boundary, video disclosure.
- `TECHNICAL/TECHNICAL_EVIDENCE_LEDGER.md` — searchable source.
- `TECHNICAL/PUBLIC_VIDEO_MANIFEST.json` — exact scene timings and footage policy.

## How to rebuild

- **PDF:** `proposal_final/` holds the complete LaTeX source, all figures and
  `make_figures.py` (regenerates every scientific figure from mission outputs).
  Build: `python proposal_final/make_figures.py` then run `pdflatex` twice on
  `proposal_final/BrineWatch_PFH2026_Final_Project_Proposal.tex`.
- **Video:** the delivered MP4 is final. To rebuild:
  `python brinewatch/scripts/make_public_competition_video.py` (source copy in
  `SOURCE_SCRIPTS/`) — it reads the cinematic master from `C:\bwrt\bwp26-cin1`
  and science assets that were pruned from `output/` during cleanup; restore
  them first from git history (commits `434ac0d` / `f8838ef`) if needed.
- **Figure sources:** static images used by `make_figures.py` are archived in
  `proposal_final/figures_src/`.
- **Ledger PDF:** `python brinewatch/scripts/build_technical_evidence_appendix.py`.

## Data and cost sources

- 2-D flagship and 3-D volumetric metrics: deterministic re-runs (seed 17) of
  `configs/pfh2026_flagship_demo.yaml` and `configs/pfh2026_flagship_volumetric.yaml`
  (four altitude bands 0.8/1.6/2.8/4.5 m) — outputs under `tmp/regen/`.
- In-engine mission and sonar localisation: isolated run `bwp26-fa3`
  (`C:\bwrt\bwp26-fa3\outputs\custom_holoocean_mission_20260722_093246`).
- Equal-evidence benchmark: ledger §5 (8 seeds × 3 methods, 48 readings, 300 m cap).
- Price anchors (22 July 2026): BlueROV2 from USD 4,900 (Blue Robotics);
  Omniscan 450 FS from USD 2,490 (Cerulean Sonar). Other costs are planning
  assumptions, flagged as such in the PDF.

## Headline evidence (all simulation)

- Sonar localisation: 2.35 m scored centre error, no oracle input.
- In-engine mission: 394.8 m travelled, 564 simulated CT readings, 0 collisions,
  4 safe detours (min clearance 1.85 m vs 2.0 m standoff, disclosed).
- Flagship 2-D: RMSE 0.3415 PSU, boundary F1 0.947, boundary IoU 0.900, correct
  conclusive POSSIBLE EXCEEDANCE screen.
- Volumetric 3-D: RMSE 0.477 PSU, volume IoU 0.805, reconstructed 2,051 m³ vs
  surrogate truth 2,448 m³.
- Equal-evidence benchmark: useful readings 17% / 23% / 70%, plume unresolved
  100% / 82% / 28%, conclusive 0/8 / 4/8 / 8/8 (sparse / regular / adaptive).

The plume is an explicitly disclosed demo-optimised analytic surrogate — not CFD,
not field truth. No regulatory-certification, field-accuracy or guaranteed-savings
claims are made anywhere in the public package.

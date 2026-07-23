# BrineWatch PFH2026 — final proposal source

This folder contains the complete source of the upload-ready competition PDF
(`output/final_submission/UPLOAD/BrineWatch_PFH2026_Final_Project_Proposal.pdf`).

## Contents

- `BrineWatch_PFH2026_Final_Project_Proposal.tex` — the full document (12 pages,
  portrait A4). All diagrams that are not data figures (concept scene, system
  overview, digital-twin flow, roadmap timeline, risk matrix) are TikZ vector
  graphics inside this file.
- `make_figures.py` — regenerates every data figure and photographic asset in
  `figures/` from repository mission outputs. Light editorial theme, consistent
  palette with the document.
- `figures/` — generated figures (PNG/JPG). Do not edit by hand.

## Rebuild

```
python proposal_final/make_figures.py
cd proposal_final
pdflatex -interaction=nonstopmode BrineWatch_PFH2026_Final_Project_Proposal.tex
pdflatex -interaction=nonstopmode BrineWatch_PFH2026_Final_Project_Proposal.tex
```

Requires MiKTeX (XCharter, helvet, tcolorbox, fontawesome5, tikz) and Python
with matplotlib + opencv + numpy.

## Data provenance (audited 22 July 2026)

| Figure | Source |
|---|---|
| `flagship_2d.png` | deterministic re-run of `configs/pfh2026_flagship_demo.yaml`, seed 17 → `tmp/regen/flagship2d/` (RMSE 0.3415 PSU, F1 0.947, IoU 0.900 — matches ledger §4) |
| `vol3d.png` | deterministic re-run of `configs/pfh2026_flagship_volumetric.yaml`, altitudes 0.8/1.6/2.8/4.5 m → `tmp/regen/vol3d_4band/` (RMSE 0.477, IoU 0.805, 2,051 vs 2,448 m³ — matches ledger §6) |
| `mission_map.png` | isolated custom-HoloOcean mission `bwp26-fa3` (564 samples, 394.85 m, 0 collisions — ledger §2) |
| `sonar_residual.png` | crop of `output/fasttrack/assets/sonar_localization.png` (recorded custom-HoloOcean sonar frames, 2.353 m centre error — ledger §3) |
| `benchmark.png` | illustrative sampling patterns + computed metrics from ledger §5 (8 seeds × 3 methods) |
| `still_*.jpg` | raw cinematic keyframes from `C:\bwrt\bwp26-cin1`, underwater grade v3 (same recipe as the public video; stylistic only) |
| `hero_*.jpg`, `closing_banner.jpg` | genuine HoloOcean stills from `output/submission/images` and `output/fasttrack/assets` |
| `dashboard.jpg` | `output/fasttrack/assets/digital_twin_dashboard.png` (simulation data) |

Cost figures: ledger §7 (planning ranges; price anchors Blue Robotics USD 4,900,
Cerulean USD 2,490, checked 22 July 2026).

The separate technical evidence ledger lives at
`output/final_submission/TECHNICAL/` and must accompany any claim audit.

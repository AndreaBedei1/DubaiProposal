# Submission PDF outline

Source: `BrineWatch_PFH2026_Submission_Draft.tex` (repo root; the original
two-page concept `BrineWatch_Proposal.tex/pdf` is retained unchanged).
Compiled: ~5 pages, < 1 MB (checked by `scripts/check_pdf_size.py`).

1. **Page 1 — The problem and the prototype.** Title + stage box ("Initial
   Prototype or Model"); problem statement; pipeline one-liner
   (Locate→Sense→Adapt→Reconstruct→Screen); genuine HoloOcean camera frame
   of the site + genuine ImagingSonar frame; "what exists today" paragraph.
2. **Page 2 — How it works.** Official-simulator boundaries (analytic
   surrogate, not CFD); sonar localization without privileged knowledge
   (octree finding + persistence-based localization); boundary-aware
   adaptive acquisition (explicitly not expected information gain);
   three-state screening semantics; implemented-vs-planned table.
3. **Page 3 — Validation.** 20-seed learning curves; RMSE table; honest
   interpretation (adaptive wins under scarcity; zero wrong conclusive
   screenings in 320 evaluations); detector-under-noise figure; simulated
   longitudinal campaign figure; reproducibility commands + repo link.
4. **Pages 4-5 — Impact and roadmap.** Users; why repeated low-cost surveys
   matter; 3-step deployment roadmap (water test → harbour → outfall
   pilot); limitations digest; team; global honesty footer (all figures
   genuine artifacts; simulated content labelled).

Checklist before submission: no overflow; every figure captioned with its
origin; file < 20 MB; claims cross-checked against VALIDATION_EVIDENCE.md;
add the final official-mission map figure and the team's physical-ROV photo
(placeholder currently absent — DO NOT substitute stock imagery).

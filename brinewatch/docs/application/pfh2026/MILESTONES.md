# Milestones achieved to date

Every item below is completed and evidenced by files, tests, figures or runs
in this repository (evidence paths in VALIDATION_EVIDENCE.md). Nothing
planned or in-progress is listed as achieved.

**Architecture & simulation**
- Simulator-agnostic mission architecture: the mission layer (planning,
  mapping, screening, reporting) sees only an abstract vehicle backend.
- Fast kinematic backend for statistical benchmarking (seconds per mission).
- Official HoloOcean 2.x backend with the native BlueROV2 (PID control,
  terrain following on measured altitude, collision recovery, stall
  blacklist, depth safety ceiling) — full missions complete on uneven
  terrain in two official worlds.
- Automated terrain calibration: RangeFinder sounding grid + outlier-robust
  plane fit (live: 0.06 m plane RMSE; the unrobust failure mode measured and
  documented).
- Configurable, terrain-calibrated visual outfall scene (pipe, manifold,
  risers, nozzles) with JSON geometry manifest — official spawn_prop only.

**Sensing & perception**
- Analytic brine-plume surrogate with exact seedable ground truth (dense-jet
  near field + bottom gravity current + tidal advection) — documented as a
  surrogate, not CFD.
- Virtual near-bed conductivity-temperature payload with configurable noise.
- Official ImagingSonar integration: recorded, replayable, timestamped
  frames synchronized with vehicle pose; sonar visibility of stock
  structures proven with a controlled present/absent experiment (and the
  runtime-prop octree limitation proven and documented).
- Classical sonar detector + persistence-based, no-ground-truth localization
  pipeline, with an offline evaluation harness on recorded missions and
  real-frame pytest fixtures.

**Autonomy & evaluation**
- Boundary-aware adaptive Gaussian-process survey planner and lawnmower
  baseline under identical mission phases and equal travel budget.
- GP field reconstruction with explicit posterior uncertainty.
- Three-state uncertainty-aware screening (CLEAR / REVIEW / POSSIBLE
  EXCEEDANCE): zero wrong conclusive results in 320 held-out benchmark
  evaluations; binary verdict retained for backward comparison.
- Equal-budget planner benchmark on 20 held-out seeds × 2 field families
  (static primary + dynamic tidal stress test), with per-seed records,
  checkpoint learning curves and confidence intervals.
- Simulated multi-mission site-history campaign demonstrating longitudinal
  screening of a discharge ramp-up (CLEAR → REVIEW → POSSIBLE EXCEEDANCE),
  with per-entry screening policy recorded.

**Engineering quality**
- 86 automated tests (unit + integration), all green, runnable without a
  GPU or HoloOcean; recorded-sonar fixtures keep perception tests hardware-free.
- Every mission produces a self-contained digital mission report (HTML),
  machine-readable summaries, logs and reproducible configs.
- Verified environment manifest and honest approximation ledger maintained
  alongside the code.

**Hardware readiness (not yet integrated — listed for context, not claimed)**
- Team owns a BlueROV2 and a Cerulean Omniscan SS450 side-scan sonar; the
  CT-payload retrofit BOM and a one-day controlled water-test protocol are
  specified (PHYSICAL_VALIDATION_PROTOCOL.md).

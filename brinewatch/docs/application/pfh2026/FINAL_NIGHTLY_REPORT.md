# Final nightly report — autonomous PFH 2026 preparation session (2026-07-16)

## 1. Executive summary

The repository moved from a simulation-led prototype with an oracle-fed
"sonar" to a **defensible Initial-Prototype submission package**: the
official HoloOcean demonstration mission now localizes the outfall structure
from real ImagingSonar frames with **no ground-truth access (6.4 m error
from a 17 m chart prior)**, completes LOCATE→BASELINE→SURVEY→REPORT on the
official PierHarbor world, and issues a correct three-state screening
verdict. A 20-held-out-seed benchmark (two field families) shows the
adaptive planner's advantage under scarce budget and — the headline —
**zero wrong conclusive screening results in 320 evaluations**. All
application documents, evidence assets, a compiled draft PDF (1.6 MB) and
88 green tests are in the repository. The two most consequential negative
results (runtime props invisible to the official acoustic octree;
single-ping intensity gates useless under sonar noise) are documented with
minimal reproductions and drove the final design.

## 2. Files created (main)

- `brinewatch/perception/` (sonar_diffuser_detector.py, sonar_localizer.py)
- `brinewatch/sensors/sonar_types.py`, `sonar_recorder.py`
- `brinewatch/simulation/outfall_scene.py`, `octree_cache.py`
- `brinewatch/utils/terrain.py`; `brinewatch/evaluation/screening.py`
- `configs/pfh2026_holoocean.yaml`, `benchmark_static.yaml`, `benchmark_dynamic.yaml`
- `scripts/`: run_pfh2026_demo.py, validate_sonar_visibility.py,
  explore_pierharbor.py, probe_locate_area.py, evaluate_sonar_detector.py,
  capture_scene_views.py, build_site_history_demo.py, check_pdf_size.py
- `tests/test_screening.py`, `tests/test_sonar_stack.py`,
  `tests/fixtures/pier_sonar_*.npz` (real recorded frames)
- `docs/application/pfh2026/` — all 15+ application documents + assets
- `BrineWatch_PFH2026_Submission_Draft.tex/.pdf` (repo root; the original
  two-page concept PDF is untouched)

## 3. Files modified (main)

`utils/config.py` (locator mode, chart prior, sonar/scene/screening/max-z
options), `mission/runner.py` (observe() plumbing, no-GT prior path,
locator factory, safety ceiling), `simulation/holoocean_backend.py` (sonar
sensor + get_observation, deferred scene build), `evaluation/compliance.py`
(p95/max outside-zone std), `evaluation/benchmark.py` (screening fields,
summary fractions), `visualization/report.py` (three-state banner),
`scripts/run_mission.py`, `scripts/run_benchmark.py` (seed-start), README.

## 4. Architecture changes

Observation channel (backend → runner → locator) added without breaking the
kinematic backend; localization split into an oracle-fed synthetic model
(baselines only) and the sonar pipeline (no ground truth, chart prior from
config); scene building moved from hard-coded backend spawns to a
terrain-calibrated, manifest-producing builder; screening layered on top of
the retained binary verdict.

## 5-7. HoloOcean reproducibility / scene / sonar status

- Official HoloOcean 2.3.0 + Ocean only (verified manifest;
  `environment_manifest.md`). Octree cache handled via the official API.
- Scene: 22/22 components built on measured terrain (robust plane RMSE
  0.06–0.12 m live); geometry manifest saved per run; application gallery
  captured and curated (captions.md; two batches of black frames
  root-caused to booting the camera vehicle against a stock obstacle).
- Sonar: runtime-prop invisibility **proven** (bit-identical present/absent
  frames, octree-clean, minimal repro script); stock-structure visibility
  and open-water zero-control **proven**; official fallback adopted openly
  (stock pier structure as acoustic target).

## 8. Sonar detector status

Classical detector verified on clean frames (cross-pose agreement < 1 m,
zero open-water contacts; real-frame fixtures in tests). Measured on 538
recorded noisy frames: single-ping strength gates cannot reach precision
0.9 (distributions overlap — much "clutter" is other real structures);
localization therefore uses mode-cluster spatial persistence with
chart-prior and aspect-diversity gates. The global-median consensus bug
(locks onto the clutter centroid) was found on recorded data and fixed.

## 9. Ground-truth-leakage audit

- `SonarDiffuserLocator` constructor takes no target position (tested).
- Official runs require an explicit `locator.prior_x/y` chart prior; the
  synthesized-from-truth prior path is reserved for kinematic baselines and
  logs its provenance.
- The runner no longer logs GT-derived localization error; only the
  post-mission evaluator touches ground truth.
- Fallback to the prior is loudly flagged in stdout, summary and report,
  and disqualifies the run as sonar evidence (v5 is the honest example).

## 10. Full-mission status (official evidence run v6)

`outputs/brinewatch_pfh2026_20260716_195329/`: 1364 samples, 1100/1100 m,
4 sonar detections, **localization error 6.41 m (sonar-confirmed)**,
screening POSSIBLE EXCEEDANCE — **correct vs ground truth** (P(exceed)
0.86). Collisions with unmapped stock obstacles were recovered by the
pop-up/blacklist logic (logged). In-plume RMSE for this harbor scenario is
3.17 PSU — higher than the kinematic benchmark's because the plume anchor
sits at the surveyable-box edge (shoreline-outfall geometry) and sampling
is 1.2 m above the evaluation layer; stated as-is.

## 11. Benchmark results

See BENCHMARK_REPORT.md: static family (tide frozen) and dynamic stress
test, 20 held-out seeds each (dev seeds 0–4 kept separate). Adaptive:
−11…−15 % in-plume RMSE and +17 % boundary F1 at 25–50 % budget; lawnmower
wins at saturated coverage; screening: 0/320 wrong conclusive results.

## 12-13. Application assets and documentation

`docs/application/pfh2026/`: BASELINE_AUDIT, environment_manifest,
APPLICATION_FIELDS, PROJECT_DESCRIPTION, MILESTONES, NOVELTY_AND_PRIOR_WORK
(verified sources + one explicitly marked [TO VERIFY]), TECHNICAL_STATUS,
VALIDATION_EVIDENCE, LIMITATIONS, PHYSICAL_VALIDATION_PROTOCOL,
SONAR_VALIDATION, BENCHMARK_REPORT, SCENE_ITERATION_LOG, VIDEO_STORYBOARD,
PDF_OUTLINE, VISUAL_ASSET_MANIFEST + assets/ (scene, sonar incl. gate
evidence, results incl. mission maps and site-history ledger).

## 14. Draft PDF

`BrineWatch_PFH2026_Submission_Draft.pdf` — 5 pages, **1.59 MB** (< 20 MB,
automated check `scripts/check_pdf_size.py`), compiled from source, every
figure a genuine artifact with an origin caption; visually verified page by
page. The original two-page concept PDF is retained unchanged.

## 15-16. Tests and reproduction commands

`python -m pytest tests -q` → **88 passed** (final run of this session).
Reproduction: see README "One-command demos" (kinematic demo; 20-seed
static/dynamic benchmarks with `--seed-start 100`; official demo
`python scripts/run_pfh2026_demo.py`; sonar gate; detector eval; site
history; scene captures). All verified executed this session with outputs
on disk.

## 17. Failed attempts and causes (kept honest)

1. Runtime-prop sonar visibility (strategies A–D): disproven — octree uses
   static level geometry only. → official-static fallback.
2. Demo v3/v4 "crashes": self-inflicted — a UTF-8 BOM in a PID file made
   the monitor misreport live processes as dead, and the "orphan" engines I
   then killed were the missions' own. Root-caused; BOM-safe tooling.
3. Clean-frame strength gates (100+) in the live mission: zero detections —
   noise floors z-scores; retuned from recorded data.
4. Global-median localization consensus: locked onto the clutter centroid
   (12–19 m errors on replay); replaced by mode clustering.
5. Terrain plane poisoned by structure soundings (z0 −226 m, waypoints at
   the surface): robust MAD fit + box-wide probe + depth ceiling.
6. Site-history campaign initially all-REVIEW: three separate causes found
   by cell-level diagnosis (GP train-point subsampling; std-bound vs survey
   design coupling; the unsampled last lawnmower line) — all documented in
   the script comments.
7. Scene captures black twice: boot-against-obstacle root cause (not
   resolution/window/pitch/engine overlap, each isolated one variable at a
   time); guard added.

## 18-19. Remaining P0 blockers / P1 tasks

**P0 blockers: none.** All P0 acceptance criteria are met.
P1 remaining: (a) provisional MP4 from the storyboard (assets exist;
ffmpeg assembly not done); (b) a physical-ROV photo from the team for the
PDF; (c) ≥3 HoloOcean seeds for the full mission (one clean evidence run +
one honest fallback run exist; more seeds strengthen the claim);
(d) verify the one marked bibliographic source. P2 ideas: principled
acquisition function; sidescan/imaging comparison; MAVLink skeleton;
spatially-uniform GP thinning.

## 20. Recommended next human actions

1. Read the draft PDF and APPLICATION_FIELDS.md; paste the fields into the
   portal (deadline 3 August 2026); attach the PDF.
2. Provide a real photo of the team's BlueROV2 for page 1 / the video.
3. Decide on the optional video (storyboard + all simulator assets ready).
4. Run `scripts/run_pfh2026_demo.py` 2–3 more times (different seeds) if
   you want a localization-error distribution instead of a single number.
5. Push the commits to GitHub (not pushed automatically).

## Claim audit

| Claim | Supported? | Evidence path | Notes |
|---|---|---|---|
| Official HoloOcean used (unmodified) | YES | environment_manifest.md; all scenario configs | Ocean 2.3.0 |
| Outfall structure visually implemented | YES | assets/scene/* + scene_manifest.json | terrain-calibrated props |
| Structure acoustically visible | PARTIAL — stock structures yes (proven); spawned outfall props NO (proven invisible) | assets/sonar/ + gate/ | central documented limitation + fallback |
| Automatic sonar detection | YES (clean frames; fixtures+tests) / PARTIAL under noise (persistence required) | tests/test_sonar_stack.py; assets/sonar/detector_eval.* | thresholds scene-dependent |
| Sonar-based localization (no GT) | YES | v6 run summary (error 6.41 m, sonar-confirmed: true); leakage audit §9 | one clean evidence run; v5 = honest fallback example |
| Adaptive mission completed (official world) | YES | outputs/brinewatch_pfh2026_20260716_195329/ | full budget, report generated |
| Uncertainty-aware map generated | YES | pfh_mission_map.png; plume_maps.npz | GP mean + std |
| Adaptive advantage under limited budget | YES (scoped) | benchmark records/curves | reverses at saturated coverage — stated |
| Screening never wrong-conclusive | YES (0/320) | benchmark_records_*.csv screening_outcome | REVIEW counted separately |
| Physical sensor tested | NO | — | protocol written only |
| Field deployment completed | NO | — | roadmap only |
| Compliance certification | NO (and never claimed) | LIMITATIONS.md | screening ≠ certification |

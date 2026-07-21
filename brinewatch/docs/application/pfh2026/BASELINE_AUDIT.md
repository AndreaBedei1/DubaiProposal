# Baseline audit — PFH 2026 preparation session (2026-07-16)

Everything below was executed and verified on this machine before any new
implementation work. Companion file: `environment_manifest.md` (verified
environment facts).

## Repository status

- Branch `main`, clean working tree, up to date with
  `origin = https://github.com/AndreaBedei1/DubaiProposal.git`.
- Single commit `8f1e5cc "Initial part"` containing 59 tracked files:
  the two-page concept proposal (`BrineWatch_Proposal.tex/pdf`), the
  `brinewatch/` Python package (plume surrogate, GP mapper, planners,
  kinematic + HoloOcean backends, mission runner, evaluation, visualization),
  configs, scripts, tests and docs.

## Commands run and results

| Command | Result |
|---|---|
| `python -m pytest tests -q` | **65 passed** (0 failed) — historical count at audit time; current figure in VALIDATION_EVIDENCE.md |
| `python scripts/run_mission.py --config configs/mission_default.yaml` | Completed: 1775 samples, budget 1600/1600 m, rmse_plume 0.662 PSU, F1 0.81, coverage 0.92 — **binary verdict PASS vs GT FAIL** (max exceedance −0.30 PSU, P(exceed) 0.38) |
| `python scripts/run_benchmark.py --config configs/benchmark.yaml --seeds 5` | Completed. Full-budget: lawnmower rmse_plume 0.375±0.057 / F1 0.767, adaptive 0.543±0.033 / F1 0.752, coverage 0.797 vs 0.909. **Binary verdict accuracy collapsed: 0.60 / 0.20** |
| `python scripts/run_mission.py --config configs/holoocean_live.yaml` | Fresh baseline run executed this session (see `outputs/`); previous evidence: 1100 m mission, 0 stalls, rmse_plume 0.555 PSU, F1 0.81 |

## Interpretation of the baseline numbers

The default scenario's true exceedance outside the mixing zone is only a few
tenths of a PSU. Late navigation improvements (horizontal-only waypoint
arrival, baseline-transect offsets away from the outfall structures) shifted
sample placement; reconstruction error **improved** but the **binary**
PASS/FAIL verdict is unstable exactly at this fine margin — reconstructions
sit within ±0.4 PSU of the threshold with P(exceed) ≈ 0.3–0.4. This is not a
regression of the mapping stack; it is evidence that a **binary verdict is
the wrong output at the margin**, which is precisely why this session
introduces the three-state CLEAR / REVIEW / POSSIBLE EXCEEDANCE screening.

## Current simulator status

- Official HoloOcean 2.3.0 + Ocean package only (no engine modifications).
- BlueROV2 PID missions complete reliably (LOCATE→BASELINE→SURVEY→REPORT);
  terrain following, collision pop-up escape, stall blacklist all in place.
- **Sonar: NOT USED YET.** The diffuser "locator" is a synthetic
  probabilistic range/bearing detection model that reads the true outfall
  position (an oracle). No acoustic data is produced or consumed.
- Outfall scene: pipe segments + manifold + risers spawned as primitives on
  the *analytic* seabed plane; visually recognizable but partially
  floating/buried where the real terrain deviates (up to ~5 m).
- Visuals: only desktop screenshots exist; no in-sim camera captures.

## Claims currently in README/docs that are NOT (or no longer) supported

1. README headline benchmark table (0.554/0.738 etc.) — **stale**: numbers
   changed after navigation fixes; must be regenerated from the new
   static benchmark and updated.
2. "10/10 correct verdicts" — no longer true for the binary verdict at the
   current margin; superseded by three-state screening (to implement).
3. Any implication that localization is "sonar-like" — the locator is an
   oracle-fed detection model; must be renamed/refactored and replaced by a
   native simulated ImagingSonar pipeline in the official demo.
4. `planning/adaptive.py` docstring references "information gain" — the
   score is a heuristic weighted acquisition; wording must become
   "boundary-aware adaptive acquisition".
5. "$5k open-source ROV" cost framing — replace with "retrofit of an
   existing BlueROV2" + verified BOM ranges.
6. "living digital twin" — currently a per-mission snapshot; either add a
   multi-mission history layer or soften the wording.

## Implementation backlog

### P0 — mandatory for a defensible submission
- Sonar visibility gate: prove spawned props (or an official static
  fallback) appear in official ImagingSonar output; save raw evidence.
- Config-driven outfall scene module with terrain-calibrated placement,
  geometry manifest, loud failures; application-quality in-sim images.
- Sonar recorder + replay; classical detector; no-GT-leakage localization;
  post-hoc-only ground-truth evaluation.
- Full official-HoloOcean mission using sonar localization.
- Three-state screening exposed in all application-facing outputs.
- Static primary benchmark (tide frozen, ≥20 seeds, dev/eval seed split) +
  dynamic stress test; regenerate all metrics; fix README claims.
- Application documentation set + draft PDF (<20 MB) + nightly report.

### P1 — highly desirable
- Detector evaluation across poses/ranges incl. target-absent controls
  (precision/recall/localization error).
- Multi-mission site-history demonstration (clearly labelled simulated).
- Video storyboard + shot assets; provisional MP4 if ffmpeg available.
- ≥3 HoloOcean seeds for the full mission.

### P2 — stretch
- Sidescan vs imaging sonar comparison; principled acquisition function
  (integrated variance reduction) benchmarked against the heuristic;
  volumetric multi-altitude map; MAVLink backend skeleton.

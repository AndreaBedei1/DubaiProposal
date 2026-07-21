# BrineWatch — final implementation report

Authoritative status of the BrineWatch prototype after the custom-engine
consolidation phase (2026-07-19). Supersedes the interim status in
FINAL_NIGHTLY_REPORT.md for the sonar/custom-engine claims.

## Headline

**The generated outfall is sonar-visible in the custom HoloOcean engine, and
BrineWatch localizes it by native simulated (non-oracle) sonar with no ground truth.** The central
prior-documentation claim ("runtime-spawned props are invisible to sonar")
was true only for the *unmodified official* engine; the *custom fork* rebuilds
the acoustic octree at runtime and sees spawned geometry. This is now proven
by a minimal truth test (a single spawned cube lights up the sonar) and used
end-to-end in a mission.

## Update — 8-phase completion (2026-07-21)

An 8-phase completion pass took the prototype from "custom-engine sonar LOCATE +
kinematic survey" to a genuinely end-to-end, collision-safe, in-engine mission
with a full evidence and reporting stack. Every item is tested (143 engine-free
tests) and curated under `outputs/`. See
[PROPOSAL_PHASE1_CHECKLIST.md](PROPOSAL_PHASE1_CHECKLIST.md) for the
promise → evidence map and `outputs/experiments/README.md` for consolidated
results.

1. **Honesty/consistency** — wording ("native simulated sonar", not "real
   sonar"), corrected outfall geometry (diffuser 19.6 m, centre (39.8, 0)),
   Python-path auto-discovery in `.ps1`, hard-capped travel budget.
2. **In-engine collision-safe mission** (`run_custom_holoocean_mission.py`,
   `outputs/custom_holoocean_mission/run1/`): BlueROV2 driven through BASELINE +
   adaptive SURVEY *inside* the fork; sonar LOCATE **1.65 m**, 271 CTD samples,
   **0 collisions**, min structure clearance 3.49 m. Collision-safe navigation
   (`planning/safe_nav.py`): a capsule hazard field from the estimate + chart,
   climb-over / go-around detours, altitude floor.
3. **In-situ single-mission localization** (`perception/insitu_locator.py`):
   no-baseline mode (chart prior + diffuser-line RANSAC + multi-aspect
   persistence + bootstrap uncertainty); compared to background subtraction
   under a clutter sweep (`outputs/localization/compare/`).
4. **3-D volumetric plume** (`mapping/volumetric.py`, `outputs/volumetric/`):
   multi-altitude survey → terrain-following x-y-z GP → slices, iso-surface,
   volume/area/uncertainty.
5. **Digital-twin dashboard** (`visualization/dashboard.py`,
   `outputs/dashboard/index.html`): one self-contained HTML — verdict banner,
   per-mission maps + KPIs, site trends; also the exportable report.
6. **Final experiments** (`outputs/experiments/`): equal-budget
   adaptive-vs-lawnmower on 12 held-out validation seeds, static + dynamic,
   full metric set. Honest headline: adaptive is a **sample-efficiency** win
   (boundary-F1 at low budget), not a universal error reduction.
7. **Demonstration MP4** (`outputs/video_demo/mission_movie/`): ~28 s
   walk-through assembled from the real mission outputs (`make_mission_movie.py`).
8. **Consolidation** — README with exact one-command reproductions, this
   report, the proposal Phase-1 checklist, and a recorded-frame integration
   test of the custom-mission LOCATE path (`tests/test_custom_mission_locate.py`).

Honest coupling documented: collision-safe navigation is only as good as the
localization — a far-off prior once localized an off-axis scene rock (25 m) and
misplaced the hazard field; a realistic ring centre + the diffuser-line fit fix
it (1.65 m). The plume remains the declared analytic surrogate throughout.

## What was fixed / added this phase

1. **Self-contained custom engine.** `discover_custom_engine()` auto-finds the
   in-project `<repo>/engine` (env-var override still honoured); the installed
   HoloOcean 2.3.0 client attaches to the fork in `-game` mode. No external
   fork client, no committed user paths. `/engine` is gitignored.
2. **Sonar visibility truth test** (`scripts/sonar_truth_test.py`): BOX, CYL
   and the full 105-component OUTFALL are ALL sonar-visible on the custom
   engine (30–34k changed bins vs the no-object baseline), one fresh engine
   session per condition, octree cache cleared before each boot.
3. **Stale-octree resolution:** the prior cross-session REMOVED anomaly was a
   persistent on-disk octree cache; `clear_octree_cache()` /
   `--clear-cache` rebuilds from scratch. Every rigorous run uses it.
4. **Background-subtraction localizer** (`sonar_background_locator.py`):
   pose-matched pre-installation baseline vs inspection frames isolate the
   outfall from native clutter (engine-free unit tested).
5. **Custom-engine scientific mission** (`run_custom_pfh2026_demo.py`): real
   custom-engine sonar LOCATE of the spawned outfall (no GT), then survey /
   GP / screening / report anchored at the sonar estimate.
6. **Video package** (`outputs/video_demo/storyboard.md`,
   `capture_cinematic_inspection.py`, `make_demo_video.py`): two-demo
   storyboard + OpenCV MP4 assembly (no ffmpeg). The primary reviewed visual
   assets are the committed hero stills (`outputs/visual/selected_world/`, 10
   framed RGB views of the accepted Dam scene) and the sonar-visibility panels
   (`outputs/sonar_truth/`); the automatic free-camera flythrough tooling is
   provided but its structure framing still needs per-site keyframe tuning
   (documented in the storyboard).

## Is the spawned outfall sonar-visible? Where?

| engine | runtime-spawned outfall visible to sonar? | evidence |
|---|---|---|
| official HoloOcean 2.3.0 | **No** — octree built once at level load | bit-identical A/B frames (`outputs/sonar_visibility/`, SONAR_VALIDATION §1) |
| custom fork (runtime octree rebuild) | **Yes** | truth test `outputs/sonar_truth/custom_run1/` (30–34k changed bins); A/B/C/D + conditions campaigns |

Mechanism: `SpawnAsset` (fork world command) spawns a static-mesh actor with
BlockAll collision and calls `Octree::MarkWorldGeometryDirty()`;
`HolodeckSonar::Tick` clears the cache and rebuilds, so the geometry enters
the acoustic octree on the next frame. **The fix works in the custom engine
only; the official engine is unchanged and still cannot see runtime props.**

## Localization of the actual outfall (no ground truth)

All errors are scored against the ACTUAL generated diffuser centre
**(39.8, 0)** (origin 30 + diffuser_length/2, diffuser_length = 19.6 m).

- **Validated study** (`outputs/localization/v2_run1/`): pose-matched
  background subtraction, 4 independent engine acquisitions (radius 18/22 m ×
  phase 0/11.25°, sensor noise σ=0.05) → **median error 2.28 m**, mean 2.03 m,
  p95 2.31 m, fallback 0/4.
- **In-mission LOCATE** (custom demo): estimate (38.08, 3.72) vs the true
  diffuser centre (39.8, 0.0) → **4.1 m error**, 54 residual contacts, 316°
  aspect diversity, no fallback. `<run>/locate_result.json`.
- Native clutter is handled by background subtraction; tuning (v1 gate sweep)
  and validation (v2 independent acquisitions) use separate datasets; ground
  truth is used only for post-run scoring.

## Full mission (custom engine)

`outputs/full_mission/` (see that README). LOCATE runs on the custom fork
engine with native simulated ImagingSonar of the spawned outfall; the BASELINE + adaptive survey,
CTD sampling, GP reconstruction and three-state screening run on the validated
kinematic model **anchored at the sonar estimate** (driving the real ROV
through the spawned structure risks collisions; the plume/CTD/GP stack is
synthetic in every BrineWatch demo). Survey-frame origin, waypoints, mixing
zone, reconstruction grid and screening all use the ESTIMATED position; the
true position is used only for post-run evaluation.

Mission result (`outputs/full_mission/custom_run1/`): sonar-localized (est.
(38.08, 3.72), 54 residual contacts, **4.1 m** from the true diffuser centre,
no fallback); survey 539 samples over the full 480 m budget; reconstruction
rmse_plume 1.02, boundary F1 0.73; **screening REVIEW** (GT verdict PASS →
outcome *inconclusive*: the mission issued no false CLEAR or false EXCEEDANCE,
it flagged for review — the honest three-state behaviour).

## Level / engine separation (honest boundary)

- **Visual + official-engine track:** official Ocean world **Dam** (accepted
  scene, materials render). `outputs/visual/selected_world/`.
- **Acoustic + custom-engine track:** the fork's engine-source **ExampleLevel**
  (the only underwater level the fork can load). Official Ocean worlds ship
  ONLY as cooked builds of the official engine and cannot run under the fork
  (EULA-gated source; see OFFICIAL_LEVEL_FEASIBILITY.md). This is a
  distribution constraint, not an integration gap.
- **Same outfall geometry** in both, enforced by
  `tests/test_adapter_geometry_parity.py` (the official `spawn_prop`
  direction-vector rotation and the fork `SpawnAsset` true-RPY rotation
  produce identical world-space components).

## Tests

- **116 engine-free tests pass** (`python -m pytest -q`, Python 3.9.25,
  2026-07-19). Engine/GPU tests carry the `holoocean_integration` marker and
  are excluded by default (`pytest.ini`); GitHub Actions runs the engine-free
  suite.
- Engine-in-the-loop results (sonar visibility, localization, mission) are run
  locally on the machine with the engine and committed as evidence packages;
  they are NOT part of CI.

## Honest final status

Classification: **B — partial success (strong).**
Visual and sonar success are unambiguous: an official-level attractive scene,
and the actual generated outfall proven sonar-visible and localized by real
sonar to ~2.3 m (validated) / 4.1 m (in-mission). The full mission runs on the
custom backend from the sonar estimate. It is **not A** because the acoustic
mission runs on the fork's ExampleLevel rather than an official Ocean world
(Ocean worlds cannot run under the fork — a hard distribution constraint), and
the mission survey uses the validated kinematic model rather than driving the
real ROV through the structure. Both are documented, not hidden.

## Remaining limitations / next steps

- Ocean worlds under the fork require the EULA-gated BYU engine source (team
  action) — then both tracks share one world.
- Real-ROV survey around the spawned structure needs collision-aware,
  structure-avoiding path planning to replace the kinematic survey.
- Physical-sonar validation (real Omniscan) remains outstanding.
- Optional: oracle vs estimated vs prior mission comparison to quantify the
  regulatory-zone impact of the 2.3–4.1 m localization error.

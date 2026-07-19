# BrineWatch — committed evidence index

Reviewable evidence packages. Everything in `visual/`, `sonar_visibility/`,
`sonar_truth/`, `localization/`, `full_mission/` and `video_demo/` is
version-controlled; all other `outputs/` subdirectories are local working
artifacts (gitignored).

Backend legend used below:
- **kinematic** — analytic backend, no engine
- **official** — unmodified HoloOcean 2.3.0 + Ocean package
- **custom fork** — HoloOcean fork (UE 5.3 editor `-game`), runtime octree
  rebuild; **auto-discovered at `<repo>/engine`** (gitignored, never committed)

Start here: [sonar_truth/](sonar_truth/) answers the core question (are
runtime-spawned objects sonar-visible in the custom engine? **yes**), and
[full_mission/](full_mission/) is the end-to-end custom-engine mission.

| Evidence | Backend | Level | Status |
|---|---|---|---|
| [sonar_truth/custom_run1/](sonar_truth/custom_run1/) — **FINAL** minimal truth test: spawned BOX / CYL / OUTFALL each dead-ahead of the sonar; all sonar-visible (30–34k changed bins vs empty baseline) | custom fork | ExampleLevel | **FINAL — the core proof** |
| [visual/selected_world/](visual/selected_world/) — **FINAL** contact sheet + 10 inspection views + poses + scene manifest + probed terrain of outfall v2 at the SELECTED site (Dam (−100,−35), axis 165°, iteration 13, accepted) | official | **Dam (official)** | FINAL visual evidence |
| [visual/world_comparison/](visual/world_comparison/) — official-level evaluation: scored comparison.csv + per-world site sheets + selected-site scene manifest (see docs LEVEL_SELECTION.md) | official | 6 underwater Ocean worlds | FINAL selection evidence |
| [visual/flatunderwater_iter9/](visual/flatunderwater_iter9/) — contact sheet + 10 inspection views + poses + scene manifest of outfall v2 (iteration 9) | official | FlatUnderwater (official) | superseded — retained as fallback-site evidence |
| [sonar_visibility/conditions_run1/](sonar_visibility/conditions_run1/) — **FINAL** clean visibility campaign: 5 conditions in independent engine sessions (A/FULL/PIPE/RISERS/REMOVED), 8 poses × 4 bearings × 4 ranges, geometry-derived windows, raw frames + analysis + NOTES (REMOVED anomaly flagged) | custom fork | fork test level | FINAL acoustic evidence (one open anomaly documented) |
| [localization/v2_run1/](localization/v2_run1/) — **FINAL** localization study: pose-matched background subtraction, 4 independent acquisitions, median error 1.52 m, fallback 0 | custom fork | fork test level | FINAL localization evidence |
| [sonar_visibility/custom_abc_20260716/](sonar_visibility/custom_abc_20260716/) — in-session A/B/C/D experiment | custom fork | fork test level | superseded by conditions_run1 (B-phase contamination documented) |
| [localization/custom_orbit_20260716/](localization/custom_orbit_20260716/) — single-orbit gate study | custom fork | fork test level | superseded by v2_run1 (kept: shows why background modelling is required) |
| [full_mission/custom_run1/](full_mission/custom_run1/) — **FINAL** custom-engine scientific mission: real sonar LOCATE of the spawned outfall (no GT) + kinematic survey / GP map / screening anchored at the estimate; summary.json, report.html, maps, sonar frames | custom fork (LOCATE) + kinematic (survey) | ExampleLevel | FINAL mission |
| [video_demo/](video_demo/) — storyboard + cinematic flythrough package (shot list, reproduction commands) | official (cinematic) | Dam | package + storyboard |

Commands (self-contained; only `UNREAL_EDITOR_EXE` needed for the custom engine):

```
# sonar-visibility truth test (spawned object appears in sonar)
powershell -File scripts/run_sonar_truth_test.ps1 -OutDir outputs/sonar_truth_run1 -SkipOfficial
# custom-engine scientific mission (boots engine, runs demo, stops engine)
powershell -File scripts/run_custom_demo.ps1
# cinematic flythrough of the accepted Dam scene
python scripts/capture_cinematic_inspection.py
# quick kinematic mission (no engine)
python scripts/run_mission.py --config configs/mission_default.yaml
```

Raw `.npz`/`.png` are committed as plain git objects (evidence packages are a
few MB each). If a future package exceeds ~50 MB, switch those files to Git
LFS and update `.gitattributes`.

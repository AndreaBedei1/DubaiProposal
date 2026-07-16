# BrineWatch — committed evidence index

Reviewable evidence packages. Everything in `visual/`, `sonar_visibility/`,
`localization/` and `full_mission/` is version-controlled; all other
`outputs/` subdirectories are local working artifacts (gitignored).

Backend legend used below:
- **kinematic** — analytic backend, no engine
- **official** — unmodified HoloOcean 2.3.0 + Ocean package
- **custom fork** — ALAR HoloOcean fork (UE 5.3 editor `-game`), runtime
  octree rebuild; located via `HOLOOCEAN_CUSTOM_ENGINE_PATH` (never committed)

| Evidence | Backend | Level | Status |
|---|---|---|---|
| [visual/selected_world/](visual/selected_world/) — **FINAL** contact sheet + 10 inspection views + poses + scene manifest + probed terrain of outfall v2 at the SELECTED site (Dam (−100,−35), axis 165°, iteration 13, accepted) | official | **Dam (official)** | FINAL visual evidence |
| [visual/world_comparison/](visual/world_comparison/) — official-level evaluation: scored comparison.csv + per-world site sheets + selected-site scene manifest (see docs LEVEL_SELECTION.md) | official | 6 underwater Ocean worlds | FINAL selection evidence |
| [visual/flatunderwater_iter9/](visual/flatunderwater_iter9/) — contact sheet + 10 inspection views + poses + scene manifest of outfall v2 (iteration 9) | official | FlatUnderwater (official) | superseded — retained as fallback-site evidence |
| [sonar_visibility/conditions_run1/](sonar_visibility/conditions_run1/) — **FINAL** clean visibility campaign: 5 conditions in independent engine sessions (A/FULL/PIPE/RISERS/REMOVED), 8 poses × 4 bearings × 4 ranges, geometry-derived windows, raw frames + analysis + NOTES (REMOVED anomaly flagged) | custom fork | fork test level | FINAL acoustic evidence (one open anomaly documented) |
| [localization/v2_run1/](localization/v2_run1/) — **FINAL** localization study: pose-matched background subtraction, 4 independent acquisitions, median error 1.52 m, fallback 0 | custom fork | fork test level | FINAL localization evidence |
| [sonar_visibility/custom_abc_20260716/](sonar_visibility/custom_abc_20260716/) — in-session A/B/C/D experiment | custom fork | fork test level | superseded by conditions_run1 (B-phase contamination documented) |
| [localization/custom_orbit_20260716/](localization/custom_orbit_20260716/) — single-orbit gate study | custom fork | fork test level | superseded by v2_run1 (kept: shows why background modelling is required) |
| full_mission/ | custom fork + official | fork test level + Dam | pending |

Commands used (engine first, then the client script, fresh engine session per
client run):

```
python scripts/launch_custom_engine.py            # terminal 1
python scripts/validate_custom_sonar.py           # sonar A/B/C/D
python scripts/localize_custom_outfall.py         # localization orbit
python scripts/inspect_outfall_scene.py --tag iter9 --world FlatUnderwater --site 100 50 --bed -87.08 --yaw 0
```

Raw `.npz` arrays are committed as plain git objects (1–3 MB each, ~14 MB
total — below any LFS-worthy threshold). If future packages exceed ~50 MB,
switch those files to Git LFS and update `.gitattributes`.

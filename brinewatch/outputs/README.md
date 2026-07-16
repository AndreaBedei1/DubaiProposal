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
| [visual/flatunderwater_iter9/](visual/flatunderwater_iter9/) — contact sheet + 10 inspection views + poses + scene manifest of outfall v2 (iteration 9, accepted) | official | FlatUnderwater (official) | PRELIMINARY — final level selection pending |
| [sonar_visibility/custom_abc_20260716/](sonar_visibility/custom_abc_20260716/) — A/B/C/D runtime visibility experiment: manifest, per-pose metrics, difference images, raw frames | custom fork | ExampleLevel (fork-internal) | PRELIMINARY — clean re-run on the selected official level pending; B-phase contamination documented in the manifest |
| [localization/custom_orbit_20260716/](localization/custom_orbit_20260716/) — single-orbit localization study: manifest, raw frames + poses, default-gate study, gate-sweep summary | custom fork | ExampleLevel (fork-internal) | PRELIMINARY — tuning and scoring share one dataset; v2 study pending |
| visual/world_comparison/ | — | — | pending (official-level evaluation) |
| full_mission/ | custom fork | selected official level | pending |

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

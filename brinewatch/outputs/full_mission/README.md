# Full custom-engine scientific mission (Demo 1)

`custom_run1/` — end-to-end BrineWatch mission: the outfall is localized by
**native simulated ImagingSonar in the custom fork engine** (no ground truth), then surveyed and
mapped.

Reproduce:
```
$env:UNREAL_EDITOR_EXE = "<UnrealEditor.exe>"
powershell -File scripts/run_custom_demo.ps1
# or, to complete from a prior run's saved sonar LOCATE without the engine:
python scripts/run_custom_pfh2026_demo.py --reuse-locate <prior_run_dir>
```

## What ran where (honest boundary)

| stage | backend | notes |
|---|---|---|
| terrain probe, spawn outfall, BASELINE + INSPECTION sonar rings, **LOCATE** | **custom fork** (native simulated ImagingSonar, runtime octree rebuild) | the ACTUAL spawned 105-component outfall; no ground truth |
| BASELINE + adaptive SURVEY, CTD, GP reconstruction, screening, report | kinematic (validated model; collision-free) | anchored at the sonar estimate; the plume/CTD/GP stack is synthetic in every BrineWatch demo |

Driving the real ROV through the spawned structure collides (the diffuser +
risers sit in the survey area), so the survey uses the collision-free
kinematic backend, clearly labelled. The novel part — localizing the spawned
outfall by native simulated sonar — runs on the custom engine.

## Result (`custom_run1/summary.json`, `CUSTOM_DEMO_OK`)

- `spawned_outfall_sonar_visible`: **true**; `sonar_octree_refreshed`: true
- `localized_by_sonar`: **true** — estimate (38.08, 3.72) from 54 residual
  contacts, 316° aspect diversity, no fallback
- `localization_error_m_vs_diffuser_centre`: **4.1 m** (true centre used for
  scoring only, post-run)
- survey: 539 samples, full 480 m budget, anchored at the sonar estimate
- reconstruction: `rmse_plume` 1.02, `boundary_f1` 0.73
- **screening: REVIEW** (three-state); GT verdict PASS, so the outcome is
  `inconclusive` — the mission was appropriately conservative (it did not
  issue a false CLEAR or false EXCEEDANCE; it flagged for review). `prob_exceed_max` 0.28.

The survey frame (box origin, waypoints, mixing-zone reference, reconstruction
grid, map labels) is anchored at the ESTIMATED position; the true position is
used only for post-mission evaluation.

## Files

`summary.json` / `CUSTOM_DEMO_OK` (all fields), `report.html`,
`map_truth_vs_reconstruction.png`, `map_compliance.png`, `plume_maps.npz`,
`samples.csv`, `mission_log.jsonl`, `locate_result.json`,
`locate_{baseline,inspection}_frames.npz` (raw sonar), `scene_manifest.json`,
`terrain.npz`, `config_used.yaml`.

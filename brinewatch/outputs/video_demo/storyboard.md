# BrineWatch demonstration video package

Two complementary demos, both from genuine HoloOcean output:

1. **Scientific mission** (custom fork engine) — the ROV locates the ACTUAL
   spawned outfall by native simulated sonar (runtime octree rebuild), then surveys and
   maps the brine plume. Produces trajectory/map/report figures.
2. **Cinematic inspection** (official engine, accepted Dam scene) — a smooth
   free-camera flythrough of the outfall for presentation.

The sonar-visibility panel (spawned object appearing in the sonar) comes from
the truth test, which is the visual proof of the core technical claim.

## Reproduce

```powershell
$env:UNREAL_EDITOR_EXE = "C:\Program Files\Epic Games\UE_5.3\Engine\Binaries\Win64\UnrealEditor.exe"

# 1. sonar-visibility proof (spawned object appears in sonar)
powershell -File scripts\run_sonar_truth_test.ps1 -OutDir outputs\sonar_truth_run1 -SkipOfficial

# 2. scientific mission (boots the engine, runs the demo, stops the engine)
powershell -File scripts\run_custom_demo.ps1

# 3. cinematic inspection flythrough (official engine, accepted Dam scene)
python scripts\capture_cinematic_inspection.py
python scripts\make_demo_video.py --frames outputs\cinematic_Dam_*\frames --fps 24
```

## Shot list (cinematic flythrough)

Camera keyframes are interpolated with smoothstep easing; the free viewport
camera (no ROV physics jitter) dollies through the structure. Each phase
yields ~24 frames.

| # | Phase | Camera move | What the viewer sees |
|---|---|---|---|
| 1 | establishing | high, looking down at the whole system | the outfall in its seabed setting |
| 2 | descend | drop toward the diffuser | approach from above |
| 3 | approach_pipeline | move along the semi-buried approach pipe | pipe + flanges + rock berm |
| 4 | follow_pipe | glide over the transition to the diffuser | continuous pipeline into the diffuser |
| 5 | inspect_risers | rise beside the risers | 6 risers, collars, hardware at scale |
| 6 | inspect_nozzles | pan across the discharge nozzles | alternating inclined nozzles + end cap |
| 7 | orbit_out | pull out and around | three-quarter hero of the system |
| 8 | orbit_far | slow far orbit | full structure against the terrain |
| 9 | pull_back | rise to a wide close | context for the survey story |

Outputs per run: `frames/frame_*.png`, `camera_log.json`, `contact_sheet.png`,
`cinematic.mp4` (OpenCV, no ffmpeg dependency).

**Status of the auto-flythrough:** `capture_cinematic_inspection.py` produces
a smooth free-camera (`move_viewport`) path and an MP4, but the automatic
framing of the structure is terrain/world-dependent and currently needs
per-site tuning of the keyframes to keep the outfall centred. The **primary,
reviewed visual assets** for the video are therefore the committed hero stills
in [`../visual/selected_world/`](../visual/selected_world/) (10 well-framed
RGB views + contact sheet of the accepted Dam scene, captured via the proven
`inspect_outfall_scene.py` ROV-camera path) together with the sonar-visibility
panels in [`../sonar_truth/`](../sonar_truth/). The flythrough tooling is
provided for a future tuned pass.

## Narrative (matches docs/application/pfh2026/VIDEO_STORYBOARD.md)

1. hidden brine plume problem → 2. BlueROV2 descends → 3. **sonar sees the
outfall** (truth-test panel: spawned object lights up the sonar) → 4. CTD
sampling along transects → 5. adaptive sampling concentrates near the plume
boundary → 6. reconstructed map with uncertainty → 7. compliance/screening
verdict → 8. digital-twin site history.

Honesty: every clip is genuine simulator output. The scene renders with
materials on the official engine (Dam); the sonar visibility + localization
run on the custom fork engine (ExampleLevel). Both use the SAME generated
outfall geometry (`OutfallSceneBuilder`), enforced by
`tests/test_adapter_geometry_parity.py`.

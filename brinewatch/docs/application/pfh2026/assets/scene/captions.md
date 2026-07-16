# Scene image captions

All images: genuine RGB-camera output of the **official HoloOcean 2.3.0**
simulator, world **PierHarbor** (official Ocean package), captured by
`scripts/capture_scene_views.py` (seed-independent posed captures; scene
geometry from `scene_manifest.json`, terrain from the v6 mission's probe).
The brine plume is an analytic overlay in the data pipeline and is **never
rendered in these images**. No stock or AI-generated imagery.

| File | What it shows | Notes |
|---|---|---|
| `pier_structure_camera.png` | The survey site: stock pier piling lattice rising from the vegetated harbor floor | recon capture (explore_pierharbor.py); this stock structure is also the acoustic localization target |
| `outfall_side_view.png` | The spawned outfall hardware at the foot of the pier: seabed pipe segments running down-slope, riser with cone nozzle, lattice and kelp behind | spawned props are visual/collision geometry only (not acoustically visible — documented limitation) |
| `outfall_risers_close.png` | Close view of the diffuser: risers with nozzle heads, base collar, manifold and pipe segments among the pier braces | terrain-calibrated placement (robust plane, per-component bed) |
| `site_context_backlit.png` | Context/mood view through the pier lattice with kelp | context only; outfall hardware not legible here |
| `site_bathymetry.png` | Local seabed depth measured by the vehicle's down-looking RangeFinder on a teleport grid | measured data render (matplotlib), not a camera image |

Rejected in the iteration loop (kept under `outputs/scene_views_*`):
`clean_wide` (kelp blocking the camera), `overview_oblique` (too dark from
the near-surface angle), plus two entire black-frame capture batches whose
root cause (booting the camera vehicle against a stock obstacle) is
documented in `SCENE_ITERATION_LOG.md`.

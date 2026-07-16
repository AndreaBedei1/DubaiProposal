# Scene iteration log — outfall placement and site selection

Chronological record of the scene/site iterations (per the application
work order: do not accept the first generated image/configuration).

| # | Configuration | Observation | Change | Result |
|---|---|---|---|---|
| 1 | SimpleUnderwater, props placed on the *analytic plane* seabed | screenshots + collision log: pipe segments floating/buried where real terrain deviates (up to ~5 m); ROV collided with manifold/risers at 2 m survey altitude | documented; motivated terrain-aware placement and PierHarbor move (also driven by the sonar octree finding) | superseded |
| 2 | PierHarbor, probe grid centred on the outfall (±24 m), plain least-squares plane | soundings that hit the pier lattice poisoned the fit (z0=−226.9, RMSE 4.6 m): waypoints extrapolated to the surface, vehicle collided at z≈−1 | robust MAD-rejecting plane fit + box-wide probe grid + waypoint depth ceiling | plane RMSE 0.06–0.12 m live; sane depths |
| 3 | Scene placed from raw TerrainMap values near structures | components over lattice-polluted soundings would sit ~5 m high | per-component plane-fallback rule (>3 m deviation ⇒ use robust plane) | 22/22 components placed; manifest saved per run |
| 4 | Survey box x∈[416,516], y≤−624 | collision line at x≈450.8 spanning 20 m in y (continuous quay wall), plus hits on the diffuser lattice itself; wall-climb excursions | box redefined to the water side: x∈[453,516], y≤−634 (outfall just outside the box, like a real shoreline outfall) | v6: LOCATE clean, 1 recovered collision in baseline |
| 5 | Camera captures with the mission scenario | mission runs have no camera (compute cost) | dedicated `scripts/capture_scene_views.py`: 6 posed views with the RGB camera, terrain reused from the run's terrain.npz | final gallery under assets/scene/ |

| 6 | Camera captures, window 1280×720 / capture 1600×900, boot at (outfall−20 m S) | ALL frames black (pixel mean 0) across two batches; sensors fine | one-variable isolation: resolution innocent, window innocent, pitch innocent — the boot location placed the vehicle against a stock obstacle (~(457,−645), the same one the v6 mission bumped), breaking camera rendering for the whole session | boot moved to verified open water; black-frame guard added (fails loudly) |
| 7 | Final gallery at 960×540 | 6/6 views captured (pixel means 20–146); `clean_wide` rejected (kelp blocking), `overview_oblique` rejected (too dark) | selected: side view (beauty), risers close-up (technical), backlit context | assets/scene/ + captions.md |

Rejected approaches, for the record: placing every object from a single
analytic plane (visible floating/burial — iteration 1); trusting raw
soundings near structures (iteration 3); treating "clean-scene" sonar gates
as mission gates (superseded by recorded-noise evaluation — see
SONAR_VALIDATION.md).

## Visual redesign phase (outfall v2, multiport diffuser)

Work order: the generated outfall must look genuinely good in HoloOcean
screenshots BEFORE any acoustic work. Judged on real RGB captures
(`scripts/inspect_outfall_scene.py`, 10 structured viewpoints + contact
sheet per iteration; every screenshot below is a genuine render).

| # | Site / change | Observation on the contact sheet | Verdict |
|---|---|---|---|
| v2-1 | PierHarbor (485,−668), first v2 build | site inside a kelp forest under the pier deck; structure unreadable | site rejected |
| v2-2 | PierHarbor (562,−678) | site directly under a moored ship hull (dark, absurd context) | site rejected |
| v2-3..5 | SimpleUnderwater (three sites) | bumpy 10 m relief: pipe chords under bumps read as monoliths; midpoint-z + endpoint-pitch segments produced sawtooth joints → replaced with shared-node chain + grade clamp | world rejected (relief), geometry fix kept |
| v2-6 | FlatUnderwater (100,50), bed −87.08, node-chain pipeline | flat well-lit stage, but ALL pipe segments rendered as vertical drums | rotation bug isolated |
| — | rotation investigation | 23-pose calibration (south view, plan view via free viewport) + engine source: `spawn_prop` rotation is fed to UE `Conv_VectorToRotator` — it is a DIRECTION VECTOR (prop local +X aligned to it, roll 0), not [roll,pitch,yaw] as documented. Inverse recipe implemented as `prop_rotation_for_axis()` | root cause fixed |
| v2-7 | all rotations via `prop_rotation_for_axis` | 105/105 components; pipeline lies correctly, flanges/sleepers/risers/nozzles coherent; nozzle cones oversized and all-black (silhouette), top-down view all water (ROV cannot hold pitch < −25°) | geometry accepted, dressing to fix |
| v2-8 | brass hardware (riser collars, nozzle tips), nozzle Ø 0.26→0.22, tip cone 1.5×/0.30→1.15×/0.22 | riser + nozzle assemblies read as engineered fittings; alternating discharge sides visible; berm rocks read as naval mines (big proud cobble spheres) | near-accept |
| v2-9 | berm rocks smaller/half-sunken/flattened; plan view via `move_viewport` + `ViewportCapture` | full contact sheet coherent: approach pipeline + flanges + berm → transition collar → diffuser on sleepers → 6 risers, alternating nozzles, end cap; plan view frames the whole system | **accepted** |

Proposal-grade captures from v2-9: `03_low_side_along_pipe` (approach +
flanges + berm), `04_three_quarter_risers` (hero shot of the diffuser),
`05_close_nozzles` (riser/nozzle hardware at ROV scale), `08_plan_view`
(system layout). Site adopted into `configs/pfh2026_holoocean.yaml`:
FlatUnderwater, outfall (100, 50), axis 0°, bed −87.08.

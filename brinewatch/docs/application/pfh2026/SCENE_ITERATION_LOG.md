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

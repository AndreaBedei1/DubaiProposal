# Technical status — component matrix

Statuses: **verified** (evidence exists on disk), **partially verified**,
**simulated surrogate** (works, but stands in for physics), **planned**
(specified, not implemented). "Sim" = official HoloOcean 2.3.0 / kinematic;
"Phys" = physical hardware.

| Component | Implementation | Validation evidence | Sim/Phys | Readiness | Open issue | Next step |
|---|---|---|---|---|---|---|
| ROV dynamics | HoloOcean BlueROV2 (engine Fossen dynamics), PID scheme 1; fast kinematic twin | missions complete; PID convergence verified empirically | Sim | verified | idealized navigation (no drift) | DVL/EKF noise model |
| Terrain following & safety | measured-altitude depth reference, min-altitude floor, depth ceiling, pop-up escape, stall blacklist | live missions over uneven PierHarbor/SimpleUnderwater terrain | Sim | verified | no lateral obstacle avoidance (quay wall/rock hits recovered but repeated) | local occupancy from sonar |
| Terrain calibration | RangeFinder probe grid + robust (MAD-rejected) plane fit | live: rmse 0.06 m vs 4.6 m unrobust; poisoned-fit failure documented | Sim | verified | coarse grid (16 m) | denser probe near structures |
| Outfall geometry (visual) | config-driven scene builder: pipe, manifold, 4-6 risers, nozzles, collars, on measured bed, JSON manifest | 22/22 components built in live runs; screenshots | Sim | verified (visual) | NOT acoustically visible (official octree excludes runtime props — proven) | ships with limitation note |
| Sonar (sensing) | official ImagingSonar, config-driven, 1 Hz, noise on | real frames recorded (500+/mission); stock-structure returns strong, open-water control zero | Sim | verified | ray-cast model ≠ physical sonar | Omniscan transfer via replay interface |
| Sonar detector | classical: log1p, per-row robust background, CFAR-like threshold, components, centroid → range/bearing | detects real pier structure in fixtures; open-water = 0 contacts; offline eval on recorded mission (precision/recall curve) | Sim | partially verified | gates are scene-dependent (noise raises MAD) | tuned from recorded noisy data (see SONAR_VALIDATION.md) |
| Localization (no GT) | consensus clustering + chart-prior gate + aspect diversity; explicit chart prior from config | first live LOCATE localized a structure; leakage audit clean (constructor takes no truth) | Sim | partially verified | clutter locks possible; strength gate vs noise trade-off | close-range confirmation behaviour |
| CT sensing | VirtualCTD samples analytic field at pose w/ noise | unit tests, all missions | Sim (surrogate) | simulated surrogate | no physical payload yet | EZO-EC retrofit + protocol |
| Plume field | analytic surrogate (near-field rise + bottom gravity current + tide) | structure tests; NOT CFD (documented) | Sim (surrogate) | simulated surrogate | not site physics | CFD-informed calibration later |
| Adaptive planner | boundary-aware GP acquisition (std + boundary proximity + travel + turn) | 20-seed held-out benchmark | Sim | verified | REVIEW-rate trade-off at high budget | principled acquisition (P2) |
| GP reconstruction | exact GP, anisotropic RBF, ambient prior mean | benchmarks; interpolation tests | Sim | verified | fixed hyperparams; quasi-static | spatio-temporal kernel |
| Uncertainty | posterior std maps; p95/max outside zone | screening + benchmarks | Sim | verified | calibration unquantified | reliability diagrams |
| Screening logic | three-state CLEAR/REVIEW/POSSIBLE_EXCEEDANCE, config policy | 0/320 wrong conclusive results (20-seed benchmarks); campaign ramp tracked correctly | Sim | verified | thresholds are policy defaults | authority co-design |
| Digital record / history | per-mission report.html + site_history ledger + trend plots | 6-mission simulated campaign | Sim | verified (labelled simulated) | no live database | append real missions |
| Reporting | self-contained HTML: screening banner, stats, maps, approximations ledger | every mission | Sim | verified | — | PDF export |
| Physical backend (MAVLink) | interface plan only (backend swap by design) | sim_to_real.md | Phys | planned | — | ArduSub SITL first |
| Physical CT payload | BOM + one-day protocol | PHYSICAL_VALIDATION_PROTOCOL.md | Phys | planned | sensor not purchased | purchase + bench cal |
| Physical sonar | team owns Omniscan 450 FS forward-looking imaging sonar | hardware exists; no BrineWatch integration yet | Phys | planned | domain gap | replay-driven port |

# Assumptions and approximations — the honesty ledger

> **Empirical note (live-mission feedback).** The survey altitude must stay
> close to the compliance evaluation layer: with `layer_thickness_m = 1.6`,
> flying at 3 m above the bed samples an anomaly ~3.5x weaker than at the
> 1 m evaluation altitude, and the GP (vertical length scale 1.8 m) then
> systematically underestimates the bottom layer — a PASS-biased verdict.
> Observed on live HoloOcean runs; the live config flies at 2.2 m. The same
> trade-off (sensor clearance vs layer proximity) exists on the real vehicle.

BrineWatch is built to be honest about what it simulates and what it fakes.
Every entry below states **what** is approximated, **why** the approximation
was chosen, and its **impact** on how results should be read. Code that
embodies an approximation carries a comment pointing back here.

Related: [`docs/architecture.md`](architecture.md) for where each module
sits, [`docs/holoocean_notes.md`](holoocean_notes.md) for what the installed
HoloOcean 2.3.0 actually provides, [`docs/sim_to_real.md`](sim_to_real.md)
for how each shortcut is retired on the way to a real vehicle.

---

## 1. The brine plume is an analytic surrogate, not CFD

**What.** `brinewatch/plume/model.py` (`BrinePlume`) generates the ground-
truth salinity field from closed-form expressions, inspired by the
phenomenology of dense-jet/gravity-current literature (Roberts et al.) but
not solved from physics. The exact functional form implemented:

- **Ambient column**: salinity `ambient + stratification * depth`,
  temperature `ambient + gradient * depth` (linear in depth); the seabed is
  the plane `z = seabed_z0 + slope_x * x + slope_y * y`.
- **Near field** — one Gaussian blob per diffuser port: for each of the
  `n_ports` ports (spread along the diffuser axis), a 3-D Gaussian of peak
  `nearfield_peak_anomaly_psu` centred half of `nearfield_offset_m`
  downstream of the port at height `riser_height_m + rise_height_m` above
  the seabed, with horizontal scale `nearfield_sigma_xy_m` and vertical
  scale `nearfield_sigma_z_m`. This mimics the dense jet rising, then
  collapsing.
- **Far field** — a bottom gravity current sourced at the impact point
  (`nearfield_offset_m` downstream of the outfall). With `r` the downstream
  distance and `s` the cross-stream offset:
  - downstream amplitude `1 / (1 + r / dilution_length_m)` for `r >= 0`, and
    a short exponential upstream tail `exp(r / upstream_tail_m)` for `r < 0`;
  - cross-stream Gaussian `exp(-0.5 (s / width)^2)` with linear width growth
    `width = farfield_initial_width_m + farfield_spread_rate * max(r, 0)`;
  - vertical decay `exp(-h / layer_thickness_m)` with `h` the height above
    the seabed (an exponential bottom-hugging layer);
  - overall peak `farfield_peak_anomaly_psu`.
- **Total anomaly** = near field + far field, clipped so salinity never
  exceeds the discharge salinity.
- **Tide**: the whole anomaly pattern is advected rigidly along the current
  axis by `tide_amplitude_m * sin(2 pi t / tide_period_s)` — the field is
  evaluated at the tide-corrected position. There is no mixing history, no
  turbulence, no eddies.
- **Temperature anomaly** = `temperature_anomaly_ratio` × salinity anomaly
  (perfectly correlated tracers).

**Why.** The whole point of BrineWatch is to *score* sampling strategies and
reconstructions quantitatively — which requires knowing the exact ground
truth at every point and time. A CFD solution would be expensive, hard to
seed and rerun across benchmarks, and would still be a model. The analytic
surrogate is controllable, differentiable, deterministic under a seed, cheap
to evaluate on full grids, and has realistic *structure* (rise-and-collapse
near field, spreading diluting bottom layer, tidal excursion).

**Impact.** Absolute PSU numbers, dilution rates, and plume extents must not
be quoted as predictions for any real site. Comparative results — adaptive
vs lawnmower at equal budget, GP reconstruction error trends, verdict
accuracy — are meaningful because both strategies face the same field. The
plume is smoother than reality, which flatters any interpolating mapper; a
real plume's patchiness would raise all reconstruction errors and likely
*increase* the value of adaptive sampling near the boundary.

## 2. The CTD samples the analytic field

**What.** `brinewatch/sensors/ctd.py` (`VirtualCTD`) reads the true analytic
salinity/temperature at the vehicle's reported pose and adds independent
Gaussian noise (`salinity_sigma_psu`, `temperature_sigma_c`,
`depth_sigma_m`), at a fixed rate (`rate_hz`).

**Why.** HoloOcean has **no water-property field at all** — there is no
salinity or temperature to measure in the engine (verified; see
[`docs/holoocean_notes.md`](holoocean_notes.md), "Known constraints").
Sampling our own plume model is the only way to close the loop, and it is
also what guarantees ground truth is known (item 1).

**Impact.** The sensing chain is realistic in *shape* (georeferencing error
comes from the backend's navigation solution, exactly like a real payload;
sample density depends on speed and rate), but the measured values are as
smooth as the surrogate field. Sensor dynamics (conductivity-cell lag,
thermal mass, biofouling drift) are not modelled.

## 3. DiffuserLocator is a detection model, not a sonar simulation

**What.** `brinewatch/sensors/locator.py` knows the true diffuser position;
within `max_range_m` each ping detects it with probability `detect_prob` and
returns range/bearing corrupted by Gaussian noise. No acoustics, no imagery,
no false positives from clutter.

**Why.** HoloOcean 2.3.0 does ship ImagingSonar / SidescanSonar /
ProfilingSonar / SinglebeamSonar, but their octree precomputation is
expensive and building a detector on sonar imagery is a project of its own
(see the sensor table in [`docs/holoocean_notes.md`](holoocean_notes.md)).
For v1, what the mission logic needs is the *information* a sonar-plus-
detector pipeline would yield: intermittent noisy range/bearing fixes.

**Impact.** The LOCATE phase's difficulty is governed by the chosen
`detect_prob`, noise sigmas, and the prior error (`prior_sigma_m`) rather
than by acoustic physics; it is optimistic about clutter (no false alarms).
The expanding-square search, budget cap, multi-detection confirmation, and
fallback-to-prior logic are all real and transfer. Phase 2 replaces this
model with sonar-based detection (see
[`docs/sim_to_real.md`](sim_to_real.md)).

## 4. The mixing zone is scaled down to 40 m

**What.** `ComplianceConfig.mixing_zone_radius_m` defaults to 40 m. Real
discharge permits define regulatory mixing zones of roughly 100–300 m.

**Why.** The HoloOcean `SimpleUnderwater` world is about 140 × 140 m
(verified bounds ±70 m; see [`docs/holoocean_notes.md`](holoocean_notes.md)).
A realistic radius would not fit inside the world, let alone leave room to
survey beyond its edge, which is where the compliance rule is evaluated.
The plume geometry is scaled to match.

**Impact.** All distances, areas, and budgets are demo-scaled; a real
deployment multiplies the survey box, mixing-zone radius, and travel budget
together. Everything is config-driven (`configs/*.yaml`), so re-scaling is a
config change, not a code change. The *logic* of the verdict — threshold
relative to ambient, evaluation outside a radius, probability of exceedance —
is scale-free.

## 5. Budget = metres travelled, as a battery proxy

**What.** `MissionBudget` (`brinewatch/utils/types.py`) counts metres of 3-D
path actually flown; the mission hard-stops when `max_distance_m` is used.
There is no energy model: hotel load, thruster efficiency, speed-dependent
drag, and currents pushing the vehicle are all ignored.

**Why.** Distance is the simplest budget that both survey strategies consume
identically, making the lawnmower-vs-adaptive comparison fair, and it is a
reasonable first-order proxy for energy at a roughly constant survey speed.
It is also backend-independent (computed by the runner from reported
positions), so kinematic and HoloOcean missions are comparable.

**Impact.** Strategies that spend time hovering or turning are under-charged
relative to reality; missions in strong currents would consume very
different energy for the same track length. Benchmark checkpoints
(`budget.checkpoints`, via `MissionResult.budget_at_sample`) inherit the
same proxy. A real deployment would replace this with battery telemetry.

## 6. GP hyperparameters are fixed; no online optimization

**What.** `brinewatch/mapping/gp_mapper.py` uses a fixed anisotropic RBF
kernel (`length_xy_m`, `length_z_m`, `signal_sigma_psu`, `noise_sigma_psu`
from `GPConfig`) with no marginal-likelihood optimization. Above
`max_train_points` the training set is randomly subsampled (seeded). The
prior mean is the ambient salinity profile, so the GP regresses the anomaly.

**Why.** Fixed hyperparameters keep the mapper deterministic, cheap, and
identical for both planners — an online-optimized GP inside the adaptive
planner's loop would confound the sampling-strategy comparison with
hyperparameter-fitting luck, and would make the benchmark much slower.

**Impact.** Reconstruction quality depends on how well the configured length
scales match the plume; they were chosen for this scenario and would need
retuning (or online optimization, listed as future work in the module
docstring) for other plume shapes or real data. The subsampling above
`max_train_points` slightly degrades long missions' maps. The GP's
uncertainty (`std`) feeds both the adaptive planner and the
`prob_exceed_max` compliance number, so miscalibrated hyperparameters
directly affect the uncertainty-aware verdict.

## 7. HoloOcean outfall props are static decoration

**What.** `HoloOceanBackend._spawn_outfall_props` spawns pipe segments, a
diffuser manifold, and risers as static props (`sim_physics=False`), placed
relative to the *analytic* seabed plane `z = seabed_z0 + slope_x * x +
slope_y * y` — not the engine's actual terrain mesh, which is close but not
identical (measured ≈ −32…−36 m in the central area).

**Why.** The props give the viewport (and any future sonar work) a visually
and geometrically plausible outfall at the exact position the plume model
uses. Sampling the real terrain height at arbitrary points is not exposed by
the engine, so the analytic plane is the shared reference for the plume,
the survey altitude, and the props. Prop spawning failures are deliberately
non-fatal (decoration must never kill a mission), and the backend avoids
`env.reset()` because it would despawn the props (see
[`docs/holoocean_notes.md`](holoocean_notes.md)).

**Impact.** Cosmetic only: props may float slightly above or sink slightly
into the rendered seabed where the plane and the terrain disagree. The plume
field, the CTD, the locator, and the compliance evaluation all use the
analytic plane consistently, so no result depends on the engine terrain.
The real altitude over the engine terrain *is* measured (down-looking
RangeFinderSensor) and used as a safety floor for depth commands.

## 8. The kinematic backend is first-order — no hydrodynamics

**What.** `brinewatch/simulation/kinematic.py` integrates first-order
velocity dynamics: desired velocity toward the waypoint (capped by separate
horizontal/vertical speed limits), blended with time constant
`accel_tau_s`, plus optional Gaussian noise on reported position. No added
mass, drag, thruster limits, attitude dynamics, or environmental forcing.

**Why.** Benchmarks need hundreds of missions across seeds and checkpoints;
the kinematic backend runs them in seconds with zero dependencies, and its
travel distances and times are realistic enough for a budget expressed in
metres (item 5).

**Impact.** Trajectories are smoother and turns cheaper than a real ROV's;
station-keeping is perfect. The `HoloOceanBackend` provides the
higher-fidelity counterpart — the engine simulates Fossen-style rigid-body
vehicle dynamics for the BlueROV2, driven through its built-in PID position
controller (`control_scheme=1`, verified in
[`docs/holoocean_notes.md`](holoocean_notes.md)) — so the same mission can
be replayed with real dynamics to check that conclusions survive. Vehicle-
level current forcing is future work in both backends; the plume's advection
is modelled inside the analytic field instead.

# From simulation to a real BlueROV2 — deployment roadmap

The architecture was designed so that the mission layer never talks to a
simulator directly: everything above `brinewatch/simulation/` is
vehicle-agnostic. This document lists, in order, the steps that turn the
HoloOcean prototype into a harbour-ready survey system, and which modules
transfer unchanged.

Related: [`architecture.md`](architecture.md) (the backend abstraction),
[`assumptions.md`](assumptions.md) (which shortcut each step retires),
[`holoocean_notes.md`](holoocean_notes.md) (simulator facts).

## What transfers unchanged

| Module | Status on real hardware |
|---|---|
| `planning/` (lawnmower + adaptive GP planner) | unchanged — consumes `VehicleState`, returns `Waypoint` |
| `mapping/gp_mapper.py` | unchanged — consumes `CTDSample`s |
| `evaluation/compliance.py` | unchanged — regulatory rule on the reconstructed field |
| `visualization/` + HTML report | unchanged |
| `mission/runner.py` state machine | unchanged (LOCATE sensing swapped, see below) |
| `utils/config.py` scenario configs | unchanged — real sites become YAML files |

What does *not* transfer: the analytic plume (reality provides the field; the
GP map becomes the only estimate) and therefore ground-truth metrics
(`rmse_*`, `boundary_f1`) — on a real site the digital twin is validated by
cross-comparison with vessel CTD casts, not against known truth.

## Step 1 — MAVLink backend (replaces `HoloOceanBackend`)

Implement `MAVLinkBackend(SimulatorBackend)` using `pymavlink` against
ArduSub (BlueOS ships MAVLink on `udp:192.168.2.1:14550`):

- `step_toward(wp)` → `SET_POSITION_TARGET_LOCAL_NED` setpoints (ArduSub
  GUIDED/`POSHOLD`-style control loop mirrors HoloOcean's scheme-1 PID; note
  NED vs the z-up convention used here — negate z in one place, the backend).
- `VehicleState` from `LOCAL_POSITION_NED` + `ATTITUDE` + `RANGEFINDER`
  (down-looking Ping1D provides `altitude`, exactly like the simulated
  RangeFinderSensor).
- Localization: ArduSub EKF with a DVL (e.g. Water Linked A50) or USBL gives
  the position quality the GP map needs; without one, expect metre-level
  drift — log it honestly in the report.

Intermediate validation: **ArduSub SITL** (`sim_vehicle.py -v ArduSub`) lets
the identical MAVLink backend drive the real firmware in software first —
the recommended step before wet testing.

## Step 2 — Real CT payload (replaces `VirtualCTD`)

- Hardware: an I²C conductivity + temperature probe (e.g. an EC probe with an
  Atlas Scientific EZO-EC board, or an oceanographic CT cell if budget
  allows, ~200-2000 EUR) wired to the BlueROV2's I²C bus; the Bar30 already
  provides depth.
- Software: a small **BlueOS extension** (Docker container) reading the probe
  and publishing samples; topside, a `RealCTD` class implementing the same
  `maybe_sample(state) -> CTDSample` interface converts conductivity to
  practical salinity (PSS-78) using temperature and pressure.
- Calibration: two-point KCl standard before each campaign; log calibration
  coefficients into the mission log (the JSONL schema already has room).

Tank test protocol (first wet milestone): a tub with a fresh/salt-water
gradient (or a pool with a salt bag released at one corner); mission =
transect back and forth; success = the GP map reproduces the gradient sign
and magnitude. This retires the "CTD samples an analytic field" assumption
with a one-day experiment.

## Step 3 — Sonar-based diffuser localization (replaces `DiffuserLocator`)

- Real vehicle: the Cerulean **Omniscan 450 FS** forward-looking imaging sonar already owned by the team;
  a pipeline/diffuser is a strong, straight acoustic target — detection can
  start as operator-assisted (click the target in the waterfall; the code
  path only needs a `Detection(range, bearing)`).
- Simulation phase 2: HoloOcean's `SidescanSonar`/`ImagingSonar` (available
  in the installed 2.3.0, see holoocean_notes) against the spawned outfall
  props, accepting the octree precompute cost; this closes the loop between
  the detection model and simulated acoustics.

## Step 4 — Currents and drift

- Add configured currents to the HoloOcean scenario (2.x supports them) so
  vehicle dynamics feel the same advection the plume model encodes.
- On the real vehicle, estimate ambient current from DVL bottom-track vs
  commanded motion and feed it to the planner as a bias on travel cost.

## Step 5 — Harbour trial, then a real outfall

1. Harbour trial: survey a known freshwater inflow (storm drain, river mouth)
   — a real salinity anomaly with none of the permitting burden.
2. Pilot at a desalination outfall with a utility/regulator partner:
   mixing-zone radius and thresholds move from scaled demo values (40 m) to
   the site permit's real ones (100-300 m); `configs/` gains a site file.
3. Deliverable per mission: the same `report.html` digital-twin snapshot —
   which is the product.

## Honest gaps that remain after all steps

- The GP maps a *quasi-static* field; strong tidal dynamics need a
  spatio-temporal kernel (documented future work).
- Single vehicle only; multi-AUV coordination is out of scope for v1.
- Compliance verdicts on real sites are evidence for regulators, not a
  replacement for accredited monitoring until validated against vessel casts.

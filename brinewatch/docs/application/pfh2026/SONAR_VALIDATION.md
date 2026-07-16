# Sonar validation — what is proven, how, and what is not

Sensor: **official HoloOcean 2.3.0 ImagingSonar** (range-azimuth intensity
image; configured 1–40 m, 120°×20°, 512×256 bins, Rayleigh additive +
Gaussian multiplicative noise in missions). Everything below uses only the
unmodified official package.

## 1. Runtime-spawned geometry is NOT acoustically visible (proven)

Controlled experiment (`scripts/validate_sonar_visibility.py`): two engine
runs with the octree cache cleared each time (official
`delete_world_octrees`), identical poses; one spawns a large test structure
via official `spawn_prop` BEFORE any sonar tick, the other spawns nothing.
Result: **bit-identical sonar frames at all three test ranges** (z-score
contrast 0.00). The official acoustic octree is built from static level
geometry only. Evidence: `assets/sonar/gate/` + `outputs/sonar_visibility_*`.
No engine patches or private octree-refresh mechanisms were used (the
ALAR-style modified simulator is explicitly out of scope).

## 2. Stock structures ARE strongly visible (proven)

PierHarbor's pier complex (the world used by BYU's own official
imaging-sonar scenario) returns strong, structured echoes: bright piling
returns with acoustic shadows at 16–40 m; an open-water control pose returns
**zero** intensity. Evidence: `assets/sonar/pier_sonar_aimed.png` vs
`assets/sonar/pier_sonar_openwater_control.png` (+ raw arrays in outputs).
Consequence: the official mission anchors the outfall at a stock pier
structure — the spawned outfall geometry is co-located visual/collision
dressing, stated as such everywhere.

## 3. Detector on clean frames (proven)

Classical pipeline (log-compression, per-row robust background, CFAR-like
robust-z threshold, connected components, z-weighted centroid →
range/bearing): on clean frames it localizes the piling structure with
cross-pose world-frame agreement < 1 m, and produces zero contacts in open
water. Real recorded frames are pytest fixtures
(`tests/fixtures/pier_sonar_*.npz`), so this holds in CI without a GPU.

## 4. Detector under mission noise (measured, humbling, documented)

Offline evaluation on a full recorded mission (538 frames,
`scripts/evaluate_sonar_detector.py`, `assets/sonar/detector_eval.png`):
with the configured sonar noise, **contact strength no longer separates
structure from clutter** (structure p50 7.7 vs clutter p50 8.0 robust-z);
range and blob area do not separate either — largely because the "clutter"
in this harbor includes other REAL structures (a quay wall, rock outcrops).
No single-frame gate achieves precision ≥ 0.9.

## 5. Localization = spatial persistence, not single pings (design + measured)

The burden therefore moves to multi-frame evidence, with no ground-truth
access: world-frame contact estimates accumulate, and the locator reports
the **densest multi-aspect cluster near the chart prior** (mode-seeking; a
global median provably locks onto the clutter centroid — measured on the
recorded mission). Gates: chart-prior plausibility (2σ of the declared
chart uncertainty), aspect diversity ≥ 25° (vertical structures echo from
all headings; specular seabed features do not), ≥ 10 clustered hits.

## 6. What this does and does not transfer

- Transfers to the physical Omniscan/real sonar: the frame geometry, the
  record/replay workflow, the offline evaluation harness, the no-GT
  interface, and the persistence-based localization logic.
- Does NOT transfer: specific thresholds (robust-z gates are scene- and
  noise-dependent and must be re-tuned on real acoustics), and any claim of
  acoustic realism of the ray-cast model itself.
- Honest status: sonar *pipeline* validated end-to-end against official
  static structures in official HoloOcean; outfall-specific acoustic
  validation awaits either an official static-outfall asset or the physical
  trial. In structure-rich harbors, unattended structure identification is
  hard; the documented fallback is operator-assisted contact confirmation
  (a normal step in real survey practice).

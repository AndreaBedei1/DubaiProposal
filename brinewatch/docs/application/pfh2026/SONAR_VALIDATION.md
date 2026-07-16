# Sonar validation — what is proven, how, and what is not

Sensor: **official HoloOcean 2.3.0 ImagingSonar** (range-azimuth intensity
image; configured 1–40 m, 120°×20°, 512×256 bins, Rayleigh additive +
Gaussian multiplicative noise in missions). Sections 1+ use only the
unmodified official package; section 0 documents the CUSTOM fork engine
(runtime octree rebuild), clearly separated.

## 0. Custom fork engine: runtime geometry IS acoustically visible (proven)

With the custom ALAR fork (see [CUSTOM_ENGINE.md](CUSTOM_ENGINE.md)),
`scripts/smoke_custom_engine.py` attached to the fork engine (UE 5.3 -game,
ExampleLevel), captured a sonar frame, spawned a cylinder via `SpawnAsset` at
runtime, and captured again from the same pose: **frames differ**
(mean |after−before| = 2.26e-4 > 0), and the engine log shows
`HolodeckSonar: world geometry changed, rebuilding octree.` on both spawn and
`ClearSpawned`. The same runtime-spawn experiment on the OFFICIAL engine
gives bit-identical frames (section 1).

**A/B/C/D experiment on the ACTUAL generated outfall**
(`scripts/validate_custom_sonar.py`, run 2026-07-16, output
`outputs/custom_sonar_abc_20260716_224530/`): one fork-engine session,
ExampleLevel, 6 poses (4 bearings x 18 m + 2 x 28 m) around the full
93-component multiport outfall; deterministic sonar (zero noise config).

- **C (outfall via SpawnAsset) vs A (no structure)**: every pose differs;
  the difference images show a large structured signature with acoustic
  shadows at structure-consistent ranges (bright pipeline arc at 15-20 m from
  the 18 m poses); the classical detector fires with contacts up to 38k bins
  at matching ranges. In-window/out-of-window contrast ratio up to 17x at the
  head-on pose.
- **Unexpected but consistent finding**: on the FORK, phase B (outfall via the
  legacy `spawn_prop` blueprint path) is ALSO acoustically visible — the fork
  handles runtime props generally, not only SpawnAsset. `spawn_prop` props
  cannot be removed at runtime, so their signature persists through C and D.
- **C - B** isolates the SpawnAsset static meshes: crisp, well-defined
  pipeline echo arcs on top of the prop signature.
- **D (ClearSpawned)**: removes the SpawnAsset actors only (rebuild-on-removal
  confirmed); the remaining D-A difference matches the persistent B props.
- Global mean|frame difference| is a MISLEADING metric here (pose-jitter and
  background dominate, all phases ~0.014): the evidence is the localized
  contrast, the difference images (`diff_images.png`) and the detector
  contacts, not global means.

Claims boundary: "the generated outfall is sonar-visible" holds for the
CUSTOM engine only; official-engine missions still localize stock geometry.

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
  static structures in official HoloOcean. Outfall-specific acoustic
  visibility has been demonstrated in the CUSTOM HoloOcean fork (section 0:
  runtime octree rebuild, A/B/C/D experiment on the generated structure).
  Validation in the unmodified official HoloOcean engine (which cannot see
  runtime-spawned geometry) and against physical sonar data remains
  outstanding. In structure-rich harbors, unattended structure
  identification is hard; the documented fallback is operator-assisted
  contact confirmation (a normal step in real survey practice).

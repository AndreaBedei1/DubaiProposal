# Localization study on the actual outfall (custom engine)

## v2 — pose-matched background subtraction (AUTHORITATIVE, 2026-07-17)

Method: a baseline pass WITHOUT the structure records sonar frames at every
survey pose (real-survey change-detection analogue: pre-installation
baseline vs post-installation inspection). Each inspection acquisition then
subtracts the pose-matched background before detection; residual contacts
are clustered (weighted 5 m mode cluster). Native clutter cancels by
construction. No ground truth reaches the locator (truth scores only).

Campaign (`scripts/run_localization_v2_campaign.ps1`, evidence
`outputs/localization/v2_run1/`): 1 background session (64 poses: 2 radii ×
2 phases × 16 bearings, noise-free) + **4 independent orbit acquisitions**,
each in its OWN fresh engine session with sensor noise enabled
(add/mult σ = 0.05), radius ∈ {18, 22} m × phase ∈ {0°, 11.25°}:

| acquisition | estimate | error to diffuser centre | dist to axis | aspect span |
|---|---|---|---|---|
| r18 φ0 | (38.04, −1.42) | 1.42 m | 1.42 m | 315° |
| r18 φ11.25 | (37.52, −0.34) | **0.59 m** | 0.34 m | 315° |
| r22 φ0 | (39.42, −0.75) | 1.61 m | 0.75 m | 292° |
| r22 φ11.25 | (37.59, −1.57) | 1.63 m | 1.57 m | 315° |

**Summary: 4/4 independent acquisitions succeed; median error 1.52 m,
mean 1.31 m, p95 1.63 m, max 1.63 m; fallback rate 0.0.** Cross-session
pose repeatability ≤ 0.1 mm (measured in the conditions campaign), so the
background subtraction is exact up to sensor noise.

Boundary: the method assumes a pre-installation baseline over the same
waypoints exists — realistic for planned-infrastructure monitoring (the
BrineWatch use case) but not for unknown-site search, where the v1
clutter-limited result below still applies.

## v1 — single-orbit, no background model (PRELIMINARY, superseded)

Run 2026-07-16, `scripts/localize_custom_outfall.py`, output
`outputs/custom_localization_20260716_235206/`. One fork-engine session:
93-component outfall built via SpawnAsset at (30, 0), axis +x, ExampleLevel
(bed −73.47); 16-pose orbit at 20 m radius around the diffuser centre,
deterministic sonar (512×256, 1–40 m, 120°×20°); frames + synchronized poses
recorded, then the full detector + mode-cluster consensus locator ran
OFFLINE over 12 chart priors (4 bearings × 10/18/26 m offsets). No ground
truth reaches the locator (truth used for scoring only).

## Results

| gates | consensus | median err vs diffuser centre |
|---|---|---|
| mission defaults (max_area 1500, min_hits 10) | 0/12 | — |
| clean-frame profile (max_area 12000, min_hits 6) | 11/12 | 10.1 m |
| clean-frame + strength ≥ 80 | 10/12 | 8.9 m |

- The **mission-default gates fail entirely** here: they were tuned on noisy
  PierHarbor recordings where diffuse >1500-bin components are seabed
  clutter. On the fork's deterministic frames the outfall itself returns
  compact-but-large components (area p50 ≈ 2200, p90 ≈ 9500 bins), so the
  area gate rejected every true contact. Gates are DATA-DEPENDENT and must be
  profiled per sensor/noise regime — documented as a real limitation.
- With the clean-frame profile the estimate is **stable across all priors**
  (same consensus cluster regardless of prior direction/offset): estimate
  (34.1, −7.5) vs diffuser centre (39.8, 0) → 9.4 m error, ~7.5 m lateral of
  the structure axis.
- The residual offset is **scene-clutter-limited**: ExampleLevel has strong
  native returns near the site (visible in the A-phase frames of the A/B/C
  experiment); the densest contact cluster includes level geometry, not only
  the outfall. A column-mirror hypothesis was tested (fliplr ≡ reversed
  azimuth convention) and rejected (offset does not collapse).
- Practical consequence: a 9–10 m LOCATE error still places the 62×60 m
  survey box on the structure — comparable to the official-engine v6 mission
  (6.4 m on stock geometry, noisy sonar).

## Honest boundaries

- This is a single-site, single-orbit study on the fork's ExampleLevel; it
  is NOT a multi-seed benchmark and is not claimed as one.
- The "full mission with survey frame anchored at the ESTIMATED position" on
  the custom engine remains TODO (next session): requires the mission runner
  on `backend: holoocean_custom` plus an engine session per run.

# Localization study on the actual outfall (custom engine)

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

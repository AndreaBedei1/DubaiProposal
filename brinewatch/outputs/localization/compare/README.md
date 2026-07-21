# Localization mode comparison — in-situ vs background subtraction (Phase 3)

Both sonar-localization modes run on the **same** committed recorded engine
frames in `../v2_run1/` (one live orbit acquisition over the spawned outfall +
a structure-free background pass at the same poses). Truth (diffuser centre
`(39.8, 0)`) is used ONLY for scoring.

Reproduce:

```bash
python scripts/compare_localization_modes.py \
    --data outputs/localization/v2_run1 --out outputs/localization/compare
```

## Modes

| mode | needs baseline? | how it rejects clutter |
|------|-----------------|------------------------|
| **background subtraction** (`SonarBackgroundLocator`) | yes — a pre-installation pass at the same poses | subtracts the pose-matched baseline; native clutter cancels by construction |
| **in-situ single-mission** (`InSituDiffuserLocator`) | no | chart prior + diffuser-line RANSAC (1-D across-track mode along the chart bearing) + multi-aspect persistence + bootstrap uncertainty |

## Files

| file | content |
|------|---------|
| `comparison.png` | left: localization error vs synthetic clutter level for both modes (in-situ with 1σ bars); right: map of both estimates vs the true centre and chart prior at clutter 0 |
| `comparison.json` | full sweep: per-level estimates, errors, fallback, in-situ σ + calibration flags |

## Result (clutter-sensitivity sweep)

Synthetic speckle + bright false blobs are added to the LIVE frames at levels
0–3; the background pass is left clean (clutter that post-dates the baseline is
exactly what defeats change detection in the field).

| clutter | in-situ error (± 1σ) | background error |
|---------|---------------------:|-----------------:|
| 0 (clean) | 3.7 m ± 2.8 | **2.3 m** |
| 1 | 3.5 m | 3.0 m |
| 2 | 6.4 m | 6.8 m |
| 3 | **2.2 m** | 10.8 m |

**Honest reading:** background subtraction is the more accurate mode when a
clean pre-installation baseline exists and the scene is stable (2.3 m clean);
the in-situ mode is competitive with **no baseline** (3.7 m) and is far more
robust to unmodelled clutter (2.2 m vs 10.8 m at level 3), and it is the only
mode that reports an uncertainty. The two curves cross at ≈ 1 clutter unit.

Neither mode uses ground truth except for this scoring. Both place the
62 × 60 m survey box on the structure. See
`docs/application/pfh2026/CUSTOM_LOCALIZATION_STUDY.md` (§ v3, § Mode
comparison) for the full write-up; engine-free tests in
`tests/test_insitu_locator.py`.

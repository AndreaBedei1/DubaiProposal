# Volumetric plume reconstruction — curated evidence (Phase 4)

3-D (x-y-z) reconstruction of the near-bottom brine plume from a **multi-altitude**
kinematic survey. Dense brine forms a bottom-hugging layer, so a single near-bed
pass only samples one horizontal slice of it. Here the BlueROV2 surveys the site at
three altitude bands above the seabed; **all** CTD samples feed **one** anisotropic
3-D Gaussian process, which is reconstructed on a terrain-following x-y-z grid.

Reproduce:

```bash
python scripts/run_volumetric_mission.py --planner adaptive --altitudes 1.5 3.5 6.0
```

Backend is **kinematic** (fast, reproducible, deterministic per seed); the plume is
the documented **analytic simulation surrogate** (`brinewatch.plume.model.BrinePlume`),
not CFD ground truth. Reconstruction quality is scored against that surrogate for
evaluation only — the estimator never sees it.

## `adaptive_run1/`

| file | what it shows |
|------|---------------|
| `volumetric_slices.png` | 2×3 panel: GP-mean bottom layer + mid-altitude layer + vertical x-z slice (top row), GP std + ground-truth bottom + ground-truth vertical slice (bottom row) |
| `volumetric_isosurface.png` | 3-D iso-surface (salinity ≥ threshold) coloured by salinity, over the seabed surface, with the three-band ROV trajectory |
| `volumetric_summary.json` | metrics (volume, bottom area, peak, altitude extent, uncertainty) for estimate vs ground truth + reconstruction RMSE/MAE/IoU |
| `volume.npz` | full arrays: `mean`, `std`, `truth`, `X`, `Y`, `Z`, `alts`, `threshold` |

### Headline numbers (seed 42, 1770 samples over 3 altitudes)

| quantity | estimate | surrogate truth |
|----------|---------:|----------------:|
| plume volume | 5477 m³ | 3756 m³ |
| bottom compliance area (≥ threshold) | 1391 m² | 1942 m² |
| peak salinity | 69.8 PSU | 68.0 PSU |
| plume top height above bed | 8.0 m | 8.0 m |

Reconstruction vs surrogate: **RMSE 2.31 PSU, MAE 1.16 PSU, volumetric IoU 0.40**
at threshold 41.65 PSU (= ambient + regulatory margin).

### How to read it honestly

- The estimate **over-spreads** the plume volume and **under-covers** the bottom
  area — the GP smooths a sharp-edged analytic body, so it inflates the diffuse
  shell while missing the very thinnest bottom fringe. This is visible in the
  slices (softer contour than truth) and is reported, not hidden.
- `plume_body_mask` keeps only the **largest connected** above-threshold component,
  so isolated GP over-shoot cells in poorly-sampled corners are excluded from the
  volume/area figures. The raw threshold mask (with those artefacts) is recoverable
  from `volume.npz`.
- The `GP std` panel is the honest uncertainty map: lowest along the densely
  sampled track, growing toward the survey-box edges.
- The bottom-hugging physics is the environmentally relevant signal and is retained:
  the vertical x-z slice shows the high-salinity core sitting on the seabed, matching
  the ground-truth slice.

Engine-free tests for this module: `tests/test_volumetric.py`.

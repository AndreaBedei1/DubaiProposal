# Multi-session sonar conditions campaign — run 1 (2026-07-17)

Five conditions, ONE FRESH FORK-ENGINE SESSION EACH (no persistent-prop
contamination): A (none), FULL (93 components), PIPE (27), RISERS (24),
REMOVED (93 spawned then ClearSpawned). 8 poses per condition (4 bearings +
2 oblique, ranges 12/18/24/30 m), deterministic sonar, teleport-pinned poses.
Analysis: `analysis.json` (geometry-derived expected windows from the scene
manifest + commanded poses — never hand-picked).

## Confirmed

- **Pose repeatability across independent engine sessions ≤ 0.0001 m** —
  cross-session frame comparison is essentially jitter-free; the earlier
  global-mean jitter problem is eliminated by design.
- **Out-of-window differences ≈ 0** (median contrast ratios 1e5–1e6):
  everything that changes between sessions is inside the geometry-predicted
  structure window.
- FULL, PIPE and RISERS each produce clean in-window signatures at all 8
  poses: the complete outfall AND its component groups are individually
  sonar-visible on the custom engine.

## Open anomaly (flagged, not yet explained)

REMOVED does **not** return to baseline: in-window MAD ~0.002 with MORE
changed bins than FULL at several poses (e.g. b270_r18: 5536 vs 681).
The smoke test previously showed rebuild-on-removal working for a single
asset. Candidate explanations to investigate: on-disk octree cache shared
across sessions (each boot loads the previous session's cache before the
first dirty-flag rebuild), incomplete actor destruction for 93 actors, or
shadow/multipath differences from the rebuilt-empty octree. UNTIL RESOLVED,
no claim is made that runtime removal restores the acoustic baseline.

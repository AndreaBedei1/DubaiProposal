# Sonar visibility truth test — runtime-spawned objects in the custom engine

Minimal, rigorous answer to the central question: **does a runtime-spawned
object appear in the sonar image?** Each condition places one object dead-ahead
of the ROV's sonar at a controlled pose; the difference against the no-object
baseline (A) is the object's acoustic signature.

Reproduce:
```
$env:UNREAL_EDITOR_EXE = "<UnrealEditor.exe>"
powershell -File scripts/run_sonar_truth_test.ps1 -OutDir outputs/sonar_truth_run1 -SkipOfficial
# then: cp outputs/sonar_truth_run1/* outputs/sonar_truth/custom_run1/
```
Engine auto-discovered at `<repo>/engine`; the installed HoloOcean 2.3.0
client attaches (self-contained). One FRESH engine session per condition,
with the on-disk octree cache cleared before each boot (`--clear-cache`), so
every octree is built from that session's actual geometry.

## Result — custom fork engine (`custom_run1/`)

Head-on pose, difference vs the no-object baseline A:

| condition | object | changed sonar bins | mean\|diff\| | visible? |
|---|---|---|---|---|
| BOX | 2 m cube on the seabed | 33,498 | 0.0064 | **YES** |
| CYL | 0.5 m × 4 m vertical cylinder | 33,652 | 0.0065 | **YES** |
| OUTFALL | full multiport outfall (105 components) | 30,665 | 0.0046 | **YES** |

Every runtime-spawned object — from the simplest cube to the full generated
outfall — is clearly visible: tens of thousands of sonar bins change vs the
empty baseline, with a bright compact return and an acoustic shadow at the
object's range/bearing (see `custom_BOX_headon.png`, `custom_OUTFALL_headon.png`
— left panel = frame, right panel = |condition − A|).

Mechanism: the fork's `SpawnAsset` world command spawns a static-mesh actor
(BlockAll collision) and calls `Octree::MarkWorldGeometryDirty()`;
`HolodeckSonar::Tick` consumes the flag, clears the on-disk octree cache and
rebuilds, so the spawned geometry enters the acoustic octree on the next
sonar frame (engine log: `world geometry changed, rebuilding octree`).

## Official engine (contrast)

On the unmodified HoloOcean 2.3.0 engine the same runtime-spawned objects are
NOT acoustically visible (the octree is built once at level load). This was
proven earlier with bit-identical A/B sonar frames — see
`../sonar_visibility/` and `docs/application/pfh2026/SONAR_VALIDATION.md` §1.
(The official leg of this particular truth-test driver was skipped here: the
first ImagingSonar frame on the large FlatUnderwater world builds a very slow
octree; the invisibility result is already established in committed evidence.)

## Files (`custom_run1/`)

- `custom_{A,BOX,CYL,OUTFALL}.npz` — raw 512×256 sonar frames (3 poses each)
- `custom_{...}_{headon,left45,right45}.png` — frame + difference panels
- `custom_{...}.json` — pose + object manifest per condition
- `truth_test_summary.json` — per-pose stats + verdicts
- `truth_test_report.md` — generated markdown report

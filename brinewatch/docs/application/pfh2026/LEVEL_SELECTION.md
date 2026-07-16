# Official-level selection for the final demonstration

Method: every underwater world in the installed official Ocean 2.3.0 package
was evaluated with `scripts/evaluate_official_levels.py` (coarse RangeFinder
scan → candidate sites → 9×9 local probe → spawn of the SAME v2 outfall →
RGB + plan captures → luminance/relief metrics). Evidence:
`outputs/visual/world_comparison/` (committed) and
`outputs/level_eval/` (local raw). Scoring formulas are in
`scripts/summarize_level_eval.py`; the table is a decision aid, not the
decision.

## Worlds evaluated (official Ocean 2.3.0: 10 worlds, 6 underwater-capable)

| world | best site | bed (m) | local relief (m) | lum | verdict |
|---|---|---|---|---|---|
| **Dam** | **(−100, −35), yaw 165°** | **−65.9** | **11.4 (structure line 1.8)** | **142** | **SELECTED** |
| FlatUnderwater | (100, 50) | −87.1 | 0.0 | 138 | runner-up / fallback |
| Dam | (−135, −15) | −67.1 | 8.1 | 118 | one occluded view |
| Dam | (−65, −45) | −67.6 | 17.7 | 141 | relief too high |
| OpenWater | (−133, 67) | −296.7 | 11.7 | 149 | rejected: 297 m depth is implausible for a desalination outfall |
| PierHarbor | (490, −690) | ~−20 | n/a | n/a | rejected: quay wall/structures inside every candidate box (v4–v6 mission evidence); kelp/ship occlusions (v2-1, v2-2) |
| SimpleUnderwater | (20, 40) | −8..−38 | >20 | n/a | rejected: extreme relief (v2-3..5 evidence) |
| ExampleLevel (official pkg) | — | — | — | — | rejected: no usable water (demo scene, not underwater) |
| Rooms / offices / Tank | — | — | — | — | not underwater worlds |

## Why Dam (−100, −35)

- **Visual quality**: brightest consistent luminance (121–151 across views);
  natural basin between gentle mounds; dam wall + native penstock corridor as
  believable industrial context in the background (an outfall next to
  existing infrastructure is thematically right).
- **Terrain**: 11.4 m relief across the 80 m probe box, but `auto_orient`
  finds a structure line with only **1.8 m** height range — moderate,
  natural-looking terrain without burying/floating components (the exact
  criterion "moderate natural terrain variation").
- **No adjacent stock structure**: the first candidate site (−100, 0) was
  REJECTED because a native penstock ran directly alongside; the refined site
  keeps native pipes 30–60 m away at the basin edges.
- **Depth** −66 m: deeper than typical (10–60 m) but within reason.
- Tie-break vs FlatUnderwater (equal total score): the work order explicitly
  warns against "an empty, ugly test map merely because localization is
  easier". FlatUnderwater remains the documented fallback if the Dam mission
  proves un-navigable (collision evidence would trigger the swap, recorded
  here).

## Known risks at the selected site (to verify in the mission phase)

1. Survey box over 11 m relief → terrain-following + reactive pop-up are
   required (both exist and are mission-proven on PierHarbor).
2. Plan-view compositions need camera placement care (ridge occlusion seen in
   the site sheet).
3. Native penstocks within 60 m: acceptable visually; irrelevant acoustically
   on the official engine (no sonar LOCATE on the official track).

## Scope boundary (unchanged)

The ACOUSTIC track (custom fork, runtime octree rebuild) cannot run Ocean
worlds — see
[OFFICIAL_LEVEL_FEASIBILITY.md](OFFICIAL_LEVEL_FEASIBILITY.md). It runs the
fork's bundled level with the SAME outfall geometry and configuration
(adapter parity enforced by `tests/test_adapter_geometry_parity.py`).

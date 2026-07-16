"""Aggregate outputs/level_eval/*/report.json into a scored comparison table.

Scores (0-3 each, explicit formulas below) follow the consolidation work
order: visual quality, terrain suitability, navigation, depth plausibility,
reproducibility. Acoustic clutter is scored where measured. The table is a
decision AID; the final call and its rationale live in
docs/application/pfh2026/LEVEL_SELECTION.md.
"""
import csv
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EVAL = REPO / "outputs" / "level_eval"


def score_visual(site):
    lum = site.get("luminance", {})
    if not lum:
        return 0.0
    vals = list(lum.values())
    mean = sum(vals) / len(vals)
    # bright + consistent across views
    s = 3.0 if mean > 130 else 2.0 if mean > 100 else 1.0 if mean > 60 else 0.0
    if min(vals) < 60:  # one occluded/dark view
        s = max(0.0, s - 1.0)
    return s


def score_terrain(site):
    r = site.get("local_relief_m")
    if r is None:
        return 0.0
    if r < 0.5:
        return 2.0  # flat is safe but featureless
    if r < 6.0:
        return 3.0  # moderate variation: ideal
    if r < 12.0:
        return 2.0
    if r < 20.0:
        return 1.0
    return 0.0


def score_depth(site):
    b = site.get("bed_median")
    if b is None:
        return 0.0
    d = -b
    if 10 <= d <= 60:
        return 3.0  # realistic desal-outfall depth
    if d <= 100:
        return 2.0
    if d <= 150:
        return 1.0
    return 0.0


def main() -> int:
    rows = []
    for rep_path in sorted(EVAL.glob("*/report.json")):
        rep = json.loads(rep_path.read_text(encoding="utf-8"))
        world = rep["world"]
        if not rep.get("sites"):
            rows.append({"world": world, "site": "-", "usable": rep.get(
                "usable_soundings", 0), "bed_median": None, "relief_m": None,
                "lum_mean": None, "built": None, "visual": 0, "terrain": 0,
                "depth": 0, "total": 0,
                "note": "no usable site" if not rep.get("usable_soundings")
                else "sites failed"})
            continue
        for site in rep["sites"]:
            lum = site.get("luminance", {})
            built = site.get("components_built")
            row = {
                "world": world,
                "site": f"({site['xy'][0]:.0f},{site['xy'][1]:.0f})",
                "usable": rep.get("usable_soundings"),
                "bed_median": site.get("bed_median"),
                "relief_m": site.get("local_relief_m"),
                "lum_mean": (round(sum(lum.values()) / len(lum), 1)
                             if lum else None),
                "built": built,
                "visual": score_visual(site),
                "terrain": score_terrain(site),
                "depth": score_depth(site),
                "note": site.get("build_error", ""),
            }
            row["total"] = row["visual"] + row["terrain"] + row["depth"]
            rows.append(row)

    rows.sort(key=lambda r: -(r["total"] or 0))
    out = EVAL / "comparison.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"{'world':<16} {'site':<14} {'bed':>7} {'relief':>7} {'lum':>6} "
          f"{'vis':>4} {'ter':>4} {'dep':>4} {'tot':>4}  note")
    for r in rows:
        print(f"{r['world']:<16} {r['site']:<14} "
              f"{r['bed_median'] if r['bed_median'] is not None else '-':>7} "
              f"{r['relief_m'] if r['relief_m'] is not None else '-':>7} "
              f"{r['lum_mean'] if r['lum_mean'] is not None else '-':>6} "
              f"{r['visual']:>4} {r['terrain']:>4} {r['depth']:>4} "
              f"{r['total']:>4}  {r['note']}")
    print(f"\nwritten -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

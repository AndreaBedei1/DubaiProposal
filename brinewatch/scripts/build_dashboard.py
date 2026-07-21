"""Build the self-contained BrineWatch digital-twin dashboard (one HTML file).

Collects mission run dirs (each with a ``summary.json`` + figures) into detailed
cards and a site-history ledger into longitudinal trend charts, then writes a
single self-contained HTML page (embedded figures, inline-SVG charts — no server,
no external assets). See brinewatch/visualization/dashboard.py.

    python scripts/build_dashboard.py \
        [--mission DIR ...] [--history site_history/history.jsonl] \
        [--out outputs/dashboard/index.html]

With no --mission, auto-discovers the committed full missions under outputs/.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from brinewatch.visualization.dashboard import (  # noqa: E402
    build_dashboard, load_history, load_mission_card)

# committed / notable mission dirs, newest first (relative to outputs/)
DEFAULT_GLOBS = [
    "custom_holoocean_mission_*",
    "full_mission/custom_run1",
    "pfh2026_custom_*",
]


def _discover(root: Path):
    dirs = []
    for g in DEFAULT_GLOBS:
        dirs.extend(sorted(root.glob(g), reverse=True))
    # keep dirs that actually hold a mission summary, de-duplicated in order
    seen, out = set(), []
    for d in dirs:
        if d.is_dir() and (d / "summary.json").is_file() and d not in seen:
            seen.add(d)
            out.append(d)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mission", action="append", default=[],
                    help="a mission run dir (repeatable); newest first")
    ap.add_argument("--history", default=str(REPO / "site_history" / "history.jsonl"))
    ap.add_argument("--out", default=str(REPO / "outputs" / "dashboard" / "index.html"))
    ap.add_argument("--site", default="Desalination outfall (custom HoloOcean)")
    ap.add_argument("--generated", default="", help="timestamp label (pass in; "
                    "the workflow clock is not read here)")
    args = ap.parse_args()

    mission_dirs = [Path(m) for m in args.mission] or _discover(REPO / "outputs")
    cards = []
    for d in mission_dirs:
        card = load_mission_card(d)
        if card is not None:
            cards.append(card)
            print(f"[dashboard] + mission {d.name} -> {card.screening_state}")
        else:
            print(f"[dashboard] - skipped {d} (no readable summary.json)")

    history = load_history(args.history)
    print(f"[dashboard] history: {len(history)} repeated-mission entries")

    out = build_dashboard(
        cards, history, args.out, site_name=args.site,
        generated=args.generated,
        subtitle="Sonar-localized outfall · collision-safe survey · "
                 "3-state screening")
    print(f"[dashboard] wrote {out}  ({out.stat().st_size // 1024} KB, self-contained)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

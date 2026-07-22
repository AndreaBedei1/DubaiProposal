"""Generate the transparent BrineWatch cost model and feasibility figure."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def total(items):
    return [round(sum(item["range_usd"][0] for item in items), 0),
            round(sum(item["range_usd"][1] for item in items), 0)]


def midpoint(rng):
    return .5 * (rng[0] + rng[1])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(ROOT / "output" / "fasttrack" / "assets"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    new_build = [
        {"item": "BlueROV2 package, tether, lights and topside", "range_usd": [7500, 12500],
         "basis": "BlueROV2 base package publicly listed from USD 4,900; accessories are planning allowance"},
        {"item": "Omniscan 450 FS + Ethernet integration", "range_usd": [2500, 4500],
         "basis": "Cerulean lists Omniscan 450 FS from USD 2,490"},
        {"item": "ROV-grade CT payload", "range_usd": [4000, 9000],
         "basis": "quote-required planning range; miniCT-class 500 m instrument"},
        {"item": "Mechanical, power and data integration", "range_usd": [2000, 5000],
         "basis": "engineering allowance"},
        {"item": "Calibration equipment and reference standards", "range_usd": [1500, 4000],
         "basis": "planning allowance"},
        {"item": "Batteries, chargers and critical spares", "range_usd": [1500, 3500],
         "basis": "planning allowance"},
        {"item": "Topside compute and storage", "range_usd": [1500, 3000],
         "basis": "commercial workstation allowance"},
        {"item": "Cases, tools and launch safety equipment", "range_usd": [1000, 2500],
         "basis": "planning allowance"},
    ]
    incremental = [
        {"item": "ROV-grade CT payload", "range_usd": [4000, 9000]},
        {"item": "Mechanical, power and data integration", "range_usd": [2000, 5000]},
        {"item": "Calibration equipment and standards", "range_usd": [1500, 4000]},
        {"item": "Batteries and mission spares", "range_usd": [1000, 2500]},
        {"item": "Incremental compute/storage", "range_usd": [500, 2000]},
    ]
    operations = {
        "BrineWatch shore launch": {
            "range_usd_per_day": [3400, 8900],
            "components": {
                "two operators": [1200, 2400], "logistics and permits": [300, 1200],
                "maintenance and consumables": [300, 800],
                "targeted reference sampling/lab": [1000, 3000],
                "data QA and report": [600, 1500], "vessel": [0, 0],
            },
        },
        "BrineWatch small boat": {
            "range_usd_per_day": [4900, 13400],
            "components": {
                "shore-launch subtotal": [3400, 8900],
                "small workboat and crew": [1500, 4500],
            },
        },
        "Sparse manual / CTD campaign": {
            "range_usd_per_day": [5000, 12000],
            "components": {"planning scenario": [5000, 12000]},
        },
        "Conventional spatial vessel survey": {
            "range_usd_per_day": [8000, 22000],
            "components": {"planning scenario": [8000, 22000]},
        },
    }
    new_total, inc_total = total(new_build), total(incremental)
    annual_missions = 12
    amortization_years = 5
    full_amort = midpoint(new_total) / (annual_missions * amortization_years)
    inc_amort = midpoint(inc_total) / (annual_missions * amortization_years)
    conventional_mid = midpoint(operations["Conventional spatial vessel survey"]["range_usd_per_day"])
    shore_mid = midpoint(operations["BrineWatch shore launch"]["range_usd_per_day"])
    boat_mid = midpoint(operations["BrineWatch small boat"]["range_usd_per_day"])
    sparse_mid = midpoint(operations["Sparse manual / CTD campaign"]["range_usd_per_day"])
    break_even = {
        "vs_conventional_shore_missions": round(midpoint(inc_total) /
                                                  max(1, conventional_mid - shore_mid), 1),
        "vs_conventional_boat_missions": round(midpoint(inc_total) /
                                                 max(1, conventional_mid - boat_mid), 1),
        "vs_sparse_shore_missions": round(midpoint(inc_total) /
                                            max(1, sparse_mid - shore_mid), 1),
    }
    payload = {
        "currency": "USD, indicative 2026 planning ranges, excluding VAT, duties and contingency",
        "team_assets": "BlueROV2 and Omniscan 450 FS already owned",
        "full_new_build": {"items": new_build, "total_range_usd": new_total},
        "incremental_next_step": {"items": incremental, "total_range_usd": inc_total},
        "operating_cost_scenarios": operations,
        "model_assumptions": {
            "operators": 2, "on_water_mission_hours": [2.5, 4.0],
            "mobilization_hours": [1.0, 2.0], "report_hours": [4, 8],
            "missions_per_year": annual_missions,
            "equipment_amortization_years": amortization_years,
            "maintenance_pct_capital_per_year": [6, 10],
            "reference_sampling": "retained where required; BrineWatch targets it rather than replacing it",
        },
        "amortization_midpoint_usd_per_mission": {
            "full_new_build": round(full_amort), "incremental": round(inc_amort)},
        "illustrative_break_even_repeated_missions": break_even,
        "break_even_warning": ("Only an illustrative midpoint scenario. No saving is guaranteed; "
                               "if vessel, permit and accredited sampling requirements are unchanged, "
                               "the primary value is better spatial evidence, not lower cost."),
        "public_price_and_specification_anchors": [
            {"source": "Blue Robotics BlueROV2 product page", "url": "https://bluerobotics.com/store/rov/bluerov2/",
             "fact": "base package publicly listed from USD 4,900"},
            {"source": "Cerulean Sonar Omniscan imaging page", "url": "https://ceruleansonar.com/imaging/",
             "fact": "Omniscan 450 FS forward-looking sonar publicly listed from USD 2,490"},
            {"source": "Cerulean Sonar documentation", "url": "https://docs.ceruleansonar.com/c/omniscan-450",
             "fact": "450 FS is the forward-scanning 100 m / 300 m packaged model"},
            {"source": "Teledyne Valeport miniCT", "url": "https://www.valeport.co.uk/products/minict/",
             "fact": "500 m acetal option, RS232/RS485, 1-8 Hz, 0-80 mS/cm"},
        ],
    }
    (out / "feasibility_cost_model.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch
    BG, PANEL, GRID = "#06171d", "#10323b", "#28515a"
    TEXT, MUTED, TEAL, CYAN, AMBER, RED = ("#f4fbfc", "#9db7bc", "#2dd4bf",
                                           "#38bdf8", "#fbbf24", "#fb7185")
    fig = plt.figure(figsize=(16, 9), facecolor=BG)
    fig.text(.055, .935, "FEASIBILITY | TRANSPARENT PLANNING RANGES", color=TEAL,
             fontsize=10.5, weight="bold")
    fig.text(.055, .87, "Reuse the robot. Add the sensing. Repeat the evidence.",
             color=TEXT, fontsize=24, weight="bold")
    fig.text(.055, .82,
             "The team already owns the BlueROV2 and Omniscan 450 FS. Value is strongest for repeated, shore/small-boat-compatible surveys.",
             color=MUTED, fontsize=11)

    def card(x, y, w, h, title, value, body, color):
        fig.patches.append(FancyBboxPatch((x, y), w, h, transform=fig.transFigure,
                           boxstyle="round,pad=0.01,rounding_size=0.012",
                           fc=PANEL, ec=GRID, lw=1))
        fig.text(x + .04 * w, y + .76 * h, title.upper(), color=MUTED,
                 fontsize=9, weight="bold")
        fig.text(x + .04 * w, y + .47 * h, value, color=color,
                 fontsize=20, weight="bold")
        fig.text(x + .04 * w, y + .12 * h, body, color=MUTED, fontsize=8.5,
                 linespacing=1.35)
    card(.055, .58, .27, .17, "Full new build", "$22k - $44k",
         "ROV + 450 FS + CT + integration\ncalibration + spares + compute", CYAN)
    card(.365, .58, .27, .17, "Incremental next step", "$9k - $23k",
         "Given owned ROV + sonar\nCT payload is the largest open item", TEAL)
    card(.675, .58, .27, .17, "Indicative break-even", "~2 - 7 repeats",
         "Midpoint scenarios only\nnot a guaranteed saving", AMBER)

    ax = fig.add_axes([.075, .17, .57, .31])
    ax.set_facecolor("#0b252d")
    labels = ["BW\nshore", "BW\nsmall boat", "Sparse\nmanual", "Spatial\nvessel"]
    keys = list(operations)
    lows = [operations[k]["range_usd_per_day"][0] / 1000 for k in keys]
    highs = [operations[k]["range_usd_per_day"][1] / 1000 for k in keys]
    mids = [(lo + hi) / 2 for lo, hi in zip(lows, highs)]
    err = np.asarray([[m - lo for m, lo in zip(mids, lows)],
                      [hi - m for m, hi in zip(mids, highs)]])
    ax.bar(range(4), mids, yerr=err, color=[TEAL, CYAN, "#78949b", RED],
           capsize=7, alpha=.9)
    ax.set_xticks(range(4), labels, color=MUTED)
    ax.set_ylabel("USD thousands / survey day", color=MUTED)
    ax.set_title("Operating scenarios | includes targeted reference sampling",
                 color=TEXT, loc="left", fontsize=12, weight="bold")
    ax.tick_params(colors=MUTED)
    ax.grid(axis="y", color=GRID, alpha=.4)
    for spine in ax.spines.values():
        spine.set_color(GRID)
    for i, (lo, hi) in enumerate(zip(lows, highs)):
        ax.text(i, hi + .5, f"${lo:.1f}-{hi:.1f}k", ha="center", color=TEXT,
                fontsize=9, weight="bold")

    ax2 = fig.add_axes([.70, .16, .245, .33])
    ax2.axis("off")
    ax2.text(0, .95, "WHEN IT WORKS", color=TEAL, fontsize=10, weight="bold")
    ax2.text(0, .80,
             "- repeated screening campaigns\n- shore or small-workboat access\n- owned robotic hardware reused\n- same-day map supports targeted follow-up\n- inspection and screening share one mobilization",
             color=TEXT, fontsize=10.5, va="top", linespacing=1.55)
    ax2.text(0, .36, "WHEN SAVINGS MAY DISAPPEAR", color=RED,
             fontsize=10, weight="bold")
    ax2.text(0, .22,
             "If vessel, permit and accredited sampling\nrequirements remain unchanged, the value is\nbetter spatial evidence - not lower cost.",
             color=MUTED, fontsize=9.5, va="top", linespacing=1.45)
    fig.text(.055, .055,
             "Assumptions: 2 operators | 2.5-4 h on water | 12 missions/year | 5-year amortization | USD, excluding VAT/duties/contingency. Validate with local quotes.",
             color=MUTED, fontsize=9)
    fig.savefig(out / "feasibility_cost.png", dpi=180,
                facecolor=fig.get_facecolor())
    plt.close(fig)

    md = f"""# BrineWatch feasibility and cost model

All figures are indicative 2026 planning ranges in USD, excluding VAT, duties and contingency. They are not quotations or guaranteed savings.

- Full new-build capital: **${new_total[0]/1000:.0f}k-${new_total[1]/1000:.0f}k**.
- Incremental next step with the team's BlueROV2 and Omniscan 450 FS already owned: **${inc_total[0]/1000:.0f}k-${inc_total[1]/1000:.0f}k**.
- BrineWatch shore-launch operating scenario: **$3.4k-$8.9k per survey day**.
- BrineWatch small-workboat scenario: **$4.9k-$13.4k per survey day**.
- Illustrative repeated-mission break-even: roughly **2-7 missions**, depending on the comparator and launch mode.

The model assumes two operators, 2.5-4 hours on the water, 4-8 hours for QA/reporting, 12 missions per year and five-year equipment amortization. Targeted reference sampling remains in the BrineWatch operating cost because the prototype guides certified/manual sampling; it does not claim to replace it.

Economic usefulness is strongest when the hardware is reused often, the site supports shore or small-boat launch and infrastructure inspection can share the same mobilization. If vessel, permit and accredited sampling requirements remain unchanged, direct savings may disappear; the primary value is more informative spatial evidence and a repeatable site history.
"""
    (out / "FEASIBILITY.md").write_text(md, encoding="utf-8")
    print(f"[feasibility] full ${new_total[0]:.0f}-${new_total[1]:.0f}; incremental ${inc_total[0]:.0f}-${inc_total[1]:.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

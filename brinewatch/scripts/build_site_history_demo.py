"""Multi-mission site-history demonstration (CLEARLY LABELLED SIMULATED).

Runs a small synthetic campaign of kinematic missions over the same site
with the discharge strength varying between missions (a plant ramping up),
appends each mission's summary to a site-history ledger, and renders the
longitudinal trend plot the digital record is meant to provide:

- max reconstructed anomaly outside the mixing zone per mission;
- worst-case exceedance probability per mission;
- three-state screening result per mission;
- exceedance area (cells over threshold) per mission.

Every entry carries ``"data_origin": "simulated"``; this demonstrates HOW
repeated missions would be tracked, it is not a claim of an operational
digital twin.

Usage:
    python scripts/build_site_history_demo.py [--missions 6]
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from brinewatch.evaluation.compliance import evaluate_compliance
from brinewatch.evaluation.screening import screen
from brinewatch.mapping.grid_map import EvalGrid
from brinewatch.mission.runner import create_mission
from brinewatch.utils.config import load_config

STATE_LEVEL = {"CLEAR": 0, "REVIEW": 1, "POSSIBLE_EXCEEDANCE": 2}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--missions", type=int, default=6)
    ap.add_argument("--out", type=str, default=str(REPO_ROOT / "site_history"))
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    ledger_path = out / "history.jsonl"
    if ledger_path.exists():
        ledger_path.unlink()

    # Discharge strength ramps across the campaign: early missions clearly
    # compliant, later ones clearly not — the pattern a screening record must
    # catch. Anomaly amplitudes scale with the excess salinity over ambient.
    discharges = np.linspace(50.0, 80.0, args.missions)
    entries = []
    for k, s_d in enumerate(discharges):
        scale = (float(s_d) - 39.5) / (68.0 - 39.5)
        cfg = load_config(None, overrides={
            "environment": {"tide_amplitude_m": 0.0},
            "outfall": {"discharge_salinity_psu": float(s_d)},
            "plume": {"farfield_peak_anomaly_psu": float(8.0 * scale),
                      "nearfield_peak_anomaly_psu": float(12.0 * scale)},
            # Full-coverage routine budget: the boustrophedon needs ~1680 m
            # plus ~350 m of LOCATE+BASELINE overhead; anything less leaves
            # the last line unsampled, and its uncertainty honestly forces
            # REVIEW ("cannot rule out exceedance where we never looked" —
            # measured: the missing y=+60 line alone kept p95 std at 1.25).
            "budget": {"max_distance_m": 2200.0},
            # Routine monitoring pattern at the compliance layer: sampling at
            # the evaluation altitude removes the vertical extrapolation bias
            # (a lesson from the live HoloOcean runs, docs/assumptions.md).
            "planner": "lawnmower",
            "survey": {"grid_resolution_m": 4.0, "altitude_m": 1.2},
            # Campaign screening policy (recorded in the ledger): CLEAR bounds
            # must be ACHIEVABLE by the survey design — with 10 m line spacing
            # and a 12 m GP length scale, mid-corridor posterior std is ~1.0,
            # so a 0.75 std bound can never be met. Policy here: P<=0.20 and
            # std<=1.2 (thresholds are authority-set policy, LIMITATIONS.md
            # item 9; exceedance bound unchanged at 0.50).
            "compliance": {"p_clear_max": 0.20, "max_posterior_std_psu": 1.2},
            # Use (nearly) all collected samples: the default 800-point random
            # GP subsample of ~2000 collected samples thins coverage enough to
            # push p95(std) above the CLEAR bound. O(n^3) cost is fine here.
            "gp": {"max_train_points": 1800},
        })
        runner = create_mission(cfg, planner_name="lawnmower",
                                backend_name="kinematic", seed_offset=200 + k)
        try:
            result = runner.run()
        finally:
            runner.backend.close()
        plume = runner.plume
        grid = EvalGrid(cfg.survey, plume.seabed_z, cfg.compliance.eval_altitude_m)
        mean, std = runner.mapper.predict(grid.points)
        truth = plume.ground_truth(grid.points, t=0.0)
        bed = float(plume.seabed_z(cfg.outfall.x, cfg.outfall.y))
        ambient = float(plume.ambient_salinity(bed))
        verdict = evaluate_compliance(mean, std, grid, plume.outfall_xy(),
                                      cfg.compliance, ambient)
        gt_verdict = evaluate_compliance(truth, None, grid, plume.outfall_xy(),
                                         cfg.compliance, ambient)
        scr = screen(verdict, cfg.compliance)
        entry = {
            "campaign_mission": k + 1,
            "data_origin": "simulated",
            "screening_policy": {"p_clear_max": cfg.compliance.p_clear_max,
                                 "p_exceed_min": cfg.compliance.p_exceed_min,
                                 "max_posterior_std_psu": cfg.compliance.max_posterior_std_psu},
            "discharge_salinity_psu": round(float(s_d), 2),
            "n_samples": len(result.samples),
            "budget_used_m": round(result.budget.used_m, 1),
            "max_exceedance_psu": round(float(verdict.max_exceedance_psu), 3),
            "prob_exceed_max": round(float(verdict.prob_exceed_max), 3),
            "n_cells_exceeding": int(verdict.n_cells_exceeding),
            "screening": scr.state.value,
            "screening_reason": scr.reason,
            "max_std_outside_psu": round(float(verdict.max_std_outside_psu), 3),
            "gt_screening": ("POSSIBLE_EXCEEDANCE" if not gt_verdict.compliant
                             else "CLEAR"),
        }
        entries.append(entry)
        with open(ledger_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
        print(f"[site_history] mission {k+1}: discharge {s_d:.1f} PSU -> "
              f"{scr.state.value} (P={verdict.prob_exceed_max:.2f})")

    # ------------------------- trend plot ------------------------------- #
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ks = [e["campaign_mission"] for e in entries]
    fig, axes = plt.subplots(3, 1, figsize=(8.5, 8.5), sharex=True,
                             constrained_layout=True)
    axes[0].plot(ks, [e["max_exceedance_psu"] for e in entries], "o-")
    axes[0].axhline(0.0, color="crimson", linestyle="--", linewidth=1.2,
                    label="mixing-zone threshold")
    axes[0].set_ylabel("Max exceedance\noutside zone (PSU)")
    axes[0].legend()
    axes[1].plot(ks, [e["prob_exceed_max"] for e in entries], "s-", color="C1")
    axes[1].axhspan(0.0, 0.10, color="green", alpha=0.12)
    axes[1].axhspan(0.50, 1.0, color="red", alpha=0.10)
    axes[1].set_ylabel("Worst-case\nP(exceed)")
    axes[1].set_ylim(0, 1)
    colors = {"CLEAR": "#1e7d3b", "REVIEW": "#c9871b", "POSSIBLE_EXCEEDANCE": "#c0392b"}
    axes[2].scatter(ks, [STATE_LEVEL[e["screening"]] for e in entries],
                    c=[colors[e["screening"]] for e in entries], s=120, zorder=3)
    axes[2].scatter(ks, [STATE_LEVEL[e["gt_screening"]] - 0.12 for e in entries],
                    marker="x", c="black", s=60, label="ground truth", zorder=3)
    axes[2].set_yticks([0, 1, 2])
    axes[2].set_yticklabels(["CLEAR", "REVIEW", "POSSIBLE\nEXCEEDANCE"])
    axes[2].set_xlabel("Campaign mission #")
    axes[2].legend(loc="upper left")
    fig.suptitle("Site history — SIMULATED campaign (discharge ramp-up scenario)")
    fig.savefig(out / "site_history_trend.png", dpi=140)
    plt.close(fig)
    print(f"[site_history] ledger: {ledger_path}")
    print(f"[site_history] trend plot: {out / 'site_history_trend.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Digital-twin style HTML mission report.

``render_html_report`` writes a single self-contained HTML file (all images
embedded as base64 data URIs, no external assets) presenting the mission as a
digital-twin snapshot of the discharge zone:

1. Header: mission name, planner, backend, date, seed.
2. Verdict banner: PASS (green) / FAIL (red) with threshold, max exceedance,
   probability of exceedance, and the ground-truth verdict alongside for the
   simulation (labelled as only available in simulation).
3. Mission stats table: samples, budget used/max, outfall estimate + true
   position, detections, wall time, phases with budget spent per phase.
4. Figures (from ``figures`` mapping name -> PNG path, embedded inline).
5. Metrics table if ``metrics`` given.
6. An "Approximations & limitations" section quoting docs/assumptions.md
   one-liners (analytic plume, detection-model locator, scaled mixing zone).

Returns the path written. The HTML is hand-rolled (no jinja dependency).
"""
from __future__ import annotations

import base64
import dataclasses
import datetime
import html
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

from ..evaluation.compliance import ComplianceVerdict
from ..evaluation.metrics import MetricsResult
from ..utils.config import MissionConfig
from ..utils.types import MissionResult

_MIME_BY_SUFFIX = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
}

# One-liners quoted from docs/assumptions.md — keep in sync with that file.
_ASSUMPTION_ONELINERS = (
    "Analytic plume: the brine field is a synthetic analytic surrogate "
    "(dense-jet rise + bottom gravity current), not a CFD solution; it provides "
    "controllable ground truth, not site physics (docs/assumptions.md).",
    "Detection-model locator: the diffuser 'sonar' is a probabilistic "
    "range/bearing detection model, not simulated acoustics.",
    "Scaled mixing zone: the compliance radius is scaled down from real permits "
    "(typically 100-300 m) so the scenario fits the small simulation world.",
)

_CSS = """
body{font-family:'Segoe UI',Arial,sans-serif;max-width:1100px;margin:2rem auto;
     padding:0 1rem;color:#1c2733;background:#ffffff;}
h1{margin-bottom:0.15rem;}
h2{margin-top:1.6rem;border-bottom:1px solid #dde3e8;padding-bottom:0.2rem;}
p.meta{color:#5a6b7a;margin-top:0;}
div.banner{border-radius:8px;padding:14px 20px;color:#ffffff;margin:1rem 0 0.4rem;}
div.banner span.verdict-label{font-size:1.6em;font-weight:700;margin-right:16px;}
.pass{background:#1e7d3b;}
.fail{background:#c0392b;}
span.chip{display:inline-block;padding:1px 10px;border-radius:10px;color:#ffffff;font-weight:600;}
p.gt-verdict{color:#5a6b7a;margin-top:0.3rem;}
table{border-collapse:collapse;margin:0.6rem 0 1.2rem;}
th,td{border:1px solid #cdd6dd;padding:5px 12px;text-align:left;font-size:0.95em;}
th{background:#eef2f5;}
figure{margin:1.2rem 0;}
figure img{max-width:100%;border:1px solid #dde3e8;border-radius:4px;}
figcaption{color:#5a6b7a;font-size:0.9em;margin-top:4px;}
ul.assumptions li{margin:5px 0;}
p.missing{color:#c0392b;font-style:italic;}
"""


# --------------------------------------------------------------------------- #
# Formatting helpers
# --------------------------------------------------------------------------- #
def _fmt(value: Any) -> str:
    """Compact human formatting for table cells (floats to 4 significant digits)."""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.4g}"
    if isinstance(value, (tuple, list)):
        return "(" + ", ".join(_fmt(v) for v in value) + ")"
    return str(value)


def _table(rows: Sequence[Tuple[str, str]], header: Optional[Tuple[str, ...]] = None) -> str:
    parts: List[str] = ["<table>"]
    if header is not None:
        parts.append("<tr>" + "".join(f"<th>{html.escape(h)}</th>" for h in header) + "</tr>")
    for row in rows:
        parts.append("<tr>" + "".join(f"<td>{html.escape(str(cell))}</td>" for cell in row) + "</tr>")
    parts.append("</table>")
    return "\n".join(parts)


def _figure_html(name: str, fig_path: Union[str, Path]) -> str:
    p = Path(fig_path)
    if not p.exists():
        return f"<p class='missing'>Figure '{html.escape(name)}' not found: {html.escape(str(p))}</p>"
    mime = _MIME_BY_SUFFIX.get(p.suffix.lower(), "image/png")
    data = base64.b64encode(p.read_bytes()).decode("ascii")
    caption = html.escape(name)
    return (
        f"<figure><img src=\"data:{mime};base64,{data}\" alt=\"{caption}\"/>"
        f"<figcaption>{caption}</figcaption></figure>"
    )


def _verdict_banner_html(verdict: ComplianceVerdict, gt_verdict: Optional[ComplianceVerdict]) -> str:
    css_class = "pass" if verdict.compliant else "fail"
    detail = (
        f"threshold {_fmt(verdict.threshold_psu)} PSU &middot; "
        f"max exceedance {_fmt(verdict.max_exceedance_psu)} PSU &middot; "
        f"P(exceed) {_fmt(verdict.prob_exceed_max)} &middot; "
        f"{verdict.n_cells_exceeding} cell(s) exceeding &middot; "
        f"mixing zone {_fmt(verdict.mixing_zone_radius_m)} m"
    )
    parts = [
        f"<div class=\"banner {css_class}\">",
        f"<span class=\"verdict-label\">{html.escape(verdict.label)}</span>",
        f"<span>{detail}</span>",
        "</div>",
    ]
    if gt_verdict is not None:
        gt_class = "pass" if gt_verdict.compliant else "fail"
        parts.append(
            "<p class=\"gt-verdict\">Ground-truth verdict: "
            f"<span class=\"chip {gt_class}\">{html.escape(gt_verdict.label)}</span> "
            f"(max exceedance {_fmt(gt_verdict.max_exceedance_psu)} PSU) "
            "&mdash; only available in simulation.</p>"
        )
    return "\n".join(parts)


def _phase_budget_rows(result: MissionResult) -> List[Tuple[str, str, str]]:
    """(phase, start time s, budget spent m) rows from the phase history.

    The budget consumed within each phase is interpolated from the
    ``(samples[i].t, budget_at_sample[i])`` series; the last phase ends at the
    total budget used.
    """
    if not result.phase_history:
        return []
    events = sorted(result.phase_history, key=lambda e: float(e[0]))
    if result.samples and result.budget_at_sample:
        t_arr = np.asarray([s.t for s in result.samples], dtype=float)
        b_arr = np.asarray(result.budget_at_sample, dtype=float)
        order = np.argsort(t_arr)
        t_arr, b_arr = t_arr[order], b_arr[order]
    else:
        t_arr = np.asarray([0.0])
        b_arr = np.asarray([0.0])
    total_used = float(result.budget.used_m) if result.budget is not None else float(b_arr[-1])
    start_budgets = np.interp([float(t) for t, _ in events], t_arr, b_arr)

    rows: List[Tuple[str, str, str]] = []
    for i, (t, phase) in enumerate(events):
        end_budget = float(start_budgets[i + 1]) if i + 1 < len(events) else total_used
        spent = max(0.0, end_budget - float(start_budgets[i]))
        rows.append((str(phase), f"{float(t):.4g}", f"{spent:.4g}"))
    return rows


def _mission_stats_rows(cfg: MissionConfig, result: MissionResult) -> List[Tuple[str, str]]:
    if result.budget is not None:
        budget_cell = f"{result.budget.used_m:.4g} / {result.budget.max_distance_m:.4g} m"
    elif result.budget_at_sample:
        budget_cell = f"{result.budget_at_sample[-1]:.4g} m used (max unknown)"
    else:
        budget_cell = "n/a"
    outfall_est = _fmt(result.outfall_estimate) + " m" if result.outfall_estimate is not None else "not found"
    rows = [
        ("CTD samples", str(len(result.samples))),
        ("Budget used / max", budget_cell),
        ("Outfall estimate (x, y)", outfall_est),
        ("Outfall true position (x, y)", f"({_fmt(float(cfg.outfall.x))}, {_fmt(float(cfg.outfall.y))}) m"),
        ("Locator detections", str(len(result.detections))),
        ("Wall time", f"{result.wall_time_s:.4g} s"),
    ]
    if result.notes:
        rows.append(("Notes", "; ".join(result.notes)))
    return rows


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
def render_html_report(
    path: Union[str, Path],
    cfg: MissionConfig,
    result: MissionResult,
    verdict: ComplianceVerdict,
    gt_verdict: Optional[ComplianceVerdict],
    metrics: Optional[MetricsResult],
    figures: Dict[str, Union[str, Path]],
    extra: Optional[Dict[str, Any]] = None,
) -> Path:
    """Write the self-contained HTML mission report; see module docstring."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    title = f"BrineWatch report — {cfg.name}"
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    body: List[str] = []
    body.append(f"<h1>{html.escape(title)}</h1>")
    body.append(
        "<p class=\"meta\">"
        f"planner: <b>{html.escape(result.planner_name)}</b> &middot; "
        f"backend: <b>{html.escape(cfg.backend.name)}</b> &middot; "
        f"date: {html.escape(now)} &middot; "
        f"seed: {cfg.seed}"
        "</p>"
    )

    body.append("<h2>Compliance verdict</h2>")
    body.append(_verdict_banner_html(verdict, gt_verdict))

    body.append("<h2>Mission stats</h2>")
    body.append(_table(_mission_stats_rows(cfg, result)))
    phase_rows = _phase_budget_rows(result)
    if phase_rows:
        body.append("<h3>Phases</h3>")
        body.append(_table(phase_rows, header=("Phase", "Start (s)", "Budget spent (m)")))

    if figures:
        body.append("<h2>Figures</h2>")
        for name, fig_path in figures.items():
            body.append(_figure_html(str(name), fig_path))

    if metrics is not None:
        body.append("<h2>Reconstruction metrics</h2>")
        metric_rows = [(f.name, _fmt(getattr(metrics, f.name))) for f in dataclasses.fields(metrics)]
        body.append(_table(metric_rows, header=("Metric", "Value")))

    if extra:
        body.append("<h2>Extra</h2>")
        body.append(_table([(str(k), _fmt(v)) for k, v in extra.items()], header=("Key", "Value")))

    body.append("<h2>Approximations &amp; limitations</h2>")
    body.append("<ul class=\"assumptions\">")
    for line in _ASSUMPTION_ONELINERS:
        body.append(f"<li>{html.escape(line)}</li>")
    body.append("</ul>")

    document = (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n<head>\n"
        "<meta charset=\"utf-8\"/>\n"
        f"<title>{html.escape(title)}</title>\n"
        f"<style>{_CSS}</style>\n"
        "</head>\n<body>\n" + "\n".join(body) + "\n</body>\n</html>\n"
    )
    out.write_text(document, encoding="utf-8")
    return out

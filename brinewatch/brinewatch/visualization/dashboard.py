"""Self-contained BrineWatch digital-twin dashboard (single HTML file).

Streamlit / Dash / plotly are not available in this environment, so the
dashboard is a *static, self-contained* HTML page: every figure is embedded as
a base64 data URI and every chart is inline SVG, so the file opens in any
browser with no server and no external assets. It is therefore also the
"exportable report" — one file to archive or send.

Inputs are ordinary mission outputs:

* per-mission ``summary.json`` (+ its figures) → a detailed mission card;
* a site-history ledger (``history.jsonl``) of repeated missions over one site
  → the longitudinal trend charts.

The salinity field behind every mission is the documented analytic surrogate,
not a CFD plume; the footer states this. Ground-truth verdicts, where shown,
are evaluation-only.
"""
from __future__ import annotations

import base64
import html
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

# canonical figure file names a mission may carry, in display order
FIGURE_FILES = [
    ("map_compliance.png", "Compliance / screening map"),
    ("map_truth_vs_reconstruction.png", "Ground truth vs reconstruction"),
    ("volumetric_isosurface.png", "3-D plume iso-surface"),
    ("volumetric_slices.png", "3-D plume slices"),
]

_STATE_STYLE = {
    "clear": ("CLEAR", "#1b7a3d", "#e6f5ec"),
    "review": ("REVIEW", "#b8860b", "#fbf3e0"),
    "possible_exceedance": ("POSSIBLE EXCEEDANCE", "#b3261e", "#fbe9e7"),
    "unknown": ("UNKNOWN", "#555", "#eee"),
}


@dataclass
class MissionCard:
    mission_id: str
    label: str
    subtitle: str
    screening_state: str
    kpis: List[Tuple[str, str]]
    figures: List[Tuple[str, str]]          # (caption, data_uri)
    notes: List[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
def _img_data_uri(path: Path) -> Optional[str]:
    try:
        raw = Path(path).read_bytes()
    except OSError:
        return None
    return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")


def _norm_state(s: Optional[str]) -> str:
    if not s:
        return "unknown"
    k = str(s).strip().lower().replace(" ", "_")
    return k if k in _STATE_STYLE else "unknown"


def _num(d: dict, *keys):
    for k in keys:
        v = d.get(k)
        if isinstance(v, (int, float)):
            return v
    return None


def load_mission_card(run_dir, label: Optional[str] = None) -> Optional[MissionCard]:
    """Build a MissionCard from a run dir with a ``summary.json``."""
    run_dir = Path(run_dir)
    sfile = run_dir / "summary.json"
    if not sfile.is_file():
        return None
    try:
        s = json.loads(sfile.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    state = _norm_state(s.get("screening") or s.get("screening_state"))
    figs: List[Tuple[str, str]] = []
    for fname, caption in FIGURE_FILES:
        uri = _img_data_uri(run_dir / fname)
        if uri:
            figs.append((caption, uri))

    def fmt(v, unit="", nd=2):
        return "—" if v is None else f"{v:.{nd}f}{unit}"

    kpis: List[Tuple[str, str]] = []
    kpis.append(("Samples", str(_num(s, "n_samples") or "—")))
    used, mx = _num(s, "budget_used_m"), _num(s, "budget_max_m")
    kpis.append(("Budget used", f"{used:.0f} m" if used is not None else "—"))
    loc = _num(s, "localization_error_m_vs_diffuser_centre",
               "localization_error_m")
    if loc is not None:
        kpis.append(("Sonar localization error", fmt(loc, " m")))
    peak = _num(s, "peak_salinity_psu", "max_exceedance_psu")
    if peak is not None:
        kpis.append(("Peak salinity anomaly", fmt(peak, " PSU")))
    if _num(s, "rmse_plume") is not None:
        kpis.append(("Reconstruction RMSE", fmt(_num(s, "rmse_plume"), " PSU")))
    if _num(s, "boundary_f1") is not None:
        kpis.append(("Boundary F1", fmt(_num(s, "boundary_f1"), "")))
    if _num(s, "plume_volume_m3") is not None:
        kpis.append(("Plume volume", fmt(_num(s, "plume_volume_m3"), " m³", 0)))
    col = _num(s, "collisions")
    if col is not None:
        kpis.append(("Collisions", str(int(col))))
    clr = _num(s, "min_structure_clearance_m")
    if clr is not None:
        kpis.append(("Min structure clearance", fmt(clr, " m")))

    subtitle_bits = []
    if s.get("survey_backend"):
        subtitle_bits.append(str(s["survey_backend"]).split("(")[0].strip())
    if s.get("localized_by_sonar") is not None:
        subtitle_bits.append("sonar-localized" if s["localized_by_sonar"]
                             else "prior-anchored")
    notes = list(s.get("notes", []))[:4] if isinstance(s.get("notes"), list) else []
    return MissionCard(
        mission_id=run_dir.name,
        label=label or run_dir.name,
        subtitle=" · ".join(subtitle_bits),
        screening_state=state,
        kpis=kpis, figures=figs, notes=notes)


def load_history(ledger_path) -> List[dict]:
    p = Path(ledger_path)
    if not p.is_file():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


# --------------------------------------------------------------------------- #
# inline SVG helpers
# --------------------------------------------------------------------------- #
def _svg_line_chart(xs: Sequence[float], ys: Sequence[float], *, title: str,
                    ylabel: str, color: str = "#2563eb",
                    threshold: Optional[float] = None,
                    width: int = 340, height: int = 180) -> str:
    if not ys:
        return f'<div class="chart empty">{html.escape(title)}: no data</div>'
    pad_l, pad_r, pad_t, pad_b = 44, 12, 26, 26
    iw, ih = width - pad_l - pad_r, height - pad_t - pad_b
    ymin, ymax = min(ys), max(ys)
    if threshold is not None:
        ymin, ymax = min(ymin, threshold), max(ymax, threshold)
    if ymax - ymin < 1e-9:
        ymax, ymin = ymax + 1.0, ymin - 1.0
    xs_ = list(xs) if xs else list(range(len(ys)))
    xmin, xmax = min(xs_), max(xs_)
    xden = (xmax - xmin) or 1.0

    def px(x):
        return pad_l + (x - xmin) / xden * iw

    def py(y):
        return pad_t + (ymax - y) / (ymax - ymin) * ih

    pts = " ".join(f"{px(x):.1f},{py(y):.1f}" for x, y in zip(xs_, ys))
    dots = "".join(f'<circle cx="{px(x):.1f}" cy="{py(y):.1f}" r="3" '
                   f'fill="{color}"/>' for x, y in zip(xs_, ys))
    thr = ""
    if threshold is not None:
        ty = py(threshold)
        thr = (f'<line x1="{pad_l}" y1="{ty:.1f}" x2="{pad_l+iw}" y2="{ty:.1f}" '
               f'stroke="#b3261e" stroke-dasharray="4 3" stroke-width="1"/>'
               f'<text x="{pad_l+iw}" y="{ty-3:.1f}" text-anchor="end" '
               f'class="thr">threshold</text>')
    # y axis ticks (min, mid, max)
    ticks = ""
    for yy in (ymin, (ymin + ymax) / 2, ymax):
        yp = py(yy)
        ticks += (f'<text x="{pad_l-6}" y="{yp+3:.1f}" text-anchor="end" '
                  f'class="tick">{yy:.2g}</text>'
                  f'<line x1="{pad_l}" y1="{yp:.1f}" x2="{pad_l+iw}" '
                  f'y2="{yp:.1f}" class="grid"/>')
    return f'''<figure class="chart"><figcaption>{html.escape(title)}</figcaption>
<svg viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">
  {ticks}{thr}
  <polyline fill="none" stroke="{color}" stroke-width="2" points="{pts}"/>
  {dots}
  <text x="4" y="{height/2:.0f}" transform="rotate(-90 12 {height/2:.0f})"
        class="axis">{html.escape(ylabel)}</text>
</svg></figure>'''


def _verdict_timeline(states: Sequence[str], width: int = 340, height: int = 70) -> str:
    if not states:
        return ""
    n = len(states)
    step = width / max(n, 1)
    cells = ""
    for i, st in enumerate(states):
        _, _, bg = _STATE_STYLE[_norm_state(st)]
        fg = _STATE_STYLE[_norm_state(st)][1]
        cx = i * step + step / 2
        cells += (f'<circle cx="{cx:.1f}" cy="34" r="11" fill="{bg}" '
                  f'stroke="{fg}" stroke-width="2"/>'
                  f'<text x="{cx:.1f}" y="38" text-anchor="middle" '
                  f'class="tlnum">{i+1}</text>')
    return f'''<figure class="chart"><figcaption>Screening verdict per mission</figcaption>
<svg viewBox="0 0 {width} {height}" role="img" aria-label="verdict timeline">
{cells}</svg></figure>'''


# --------------------------------------------------------------------------- #
def _kpi_html(kpis: Sequence[Tuple[str, str]]) -> str:
    return "".join(f'<div class="kpi"><span class="kpi-v">{html.escape(str(v))}</span>'
                   f'<span class="kpi-l">{html.escape(k)}</span></div>'
                   for k, v in kpis)


def _card_html(card: MissionCard, active: bool) -> str:
    label, color, bg = _STATE_STYLE[card.screening_state]
    figs = "".join(
        f'<figure class="mfig"><img src="{uri}" alt="{html.escape(cap)}"/>'
        f'<figcaption>{html.escape(cap)}</figcaption></figure>'
        for cap, uri in card.figures)
    notes = ""
    if card.notes:
        notes = ("<ul class=\"notes\">" +
                 "".join(f"<li>{html.escape(n)}</li>" for n in card.notes) +
                 "</ul>")
    return f'''<section class="card mission" id="m-{html.escape(card.mission_id)}"
       style="display:{'block' if active else 'none'}">
  <div class="card-head">
    <div><h2>{html.escape(card.label)}</h2>
      <p class="sub">{html.escape(card.subtitle)}</p></div>
    <span class="badge" style="background:{bg};color:{color};border-color:{color}">{label}</span>
  </div>
  <div class="kpis">{_kpi_html(card.kpis)}</div>
  <div class="figs">{figs or '<p class="muted">no figures</p>'}</div>
  {notes}
</section>'''


def build_dashboard(cards: Sequence[MissionCard], history: Sequence[dict],
                    out_html, *, site_name: str = "Desalination outfall",
                    generated: str = "", subtitle: str = "") -> Path:
    out_html = Path(out_html)
    out_html.parent.mkdir(parents=True, exist_ok=True)

    latest = cards[0] if cards else None
    banner_state = latest.screening_state if latest else "unknown"
    b_label, b_color, b_bg = _STATE_STYLE[banner_state]

    # mission selector
    opts = "".join(
        f'<option value="m-{html.escape(c.mission_id)}">{html.escape(c.label)}</option>'
        for c in cards)
    cards_html = "".join(_card_html(c, i == 0) for i, c in enumerate(cards))

    # trend charts from the history ledger
    charts = ""
    if history:
        idx = [h.get("campaign_mission", i + 1) for i, h in enumerate(history)]
        peak = [h.get("max_exceedance_psu") for h in history]
        pexc = [h.get("prob_exceed_max") for h in history]
        area = [h.get("n_cells_exceeding") for h in history]
        states = [h.get("screening") or h.get("screening_state") or "unknown"
                  for h in history]
        if any(v is not None for v in peak):
            charts += _svg_line_chart(idx, [p for p in peak if p is not None],
                                      title="Max anomaly outside mixing zone",
                                      ylabel="PSU", color="#2563eb", threshold=0.0)
        if any(v is not None for v in pexc):
            charts += _svg_line_chart(idx, [p for p in pexc if p is not None],
                                      title="Worst-case exceedance probability",
                                      ylabel="P(exceed)", color="#b3261e",
                                      threshold=0.5)
        if any(v is not None for v in area):
            charts += _svg_line_chart(idx, [a for a in area if a is not None],
                                      title="Exceedance area (cells over threshold)",
                                      ylabel="cells", color="#7c3aed")
        charts += _verdict_timeline(states)
    trends = (f'<div class="card"><h2>Site trends — {len(history)} repeated missions</h2>'
              f'<div class="charts">{charts}</div>'
              f'<p class="muted">Longitudinal record over one site (labelled '
              f'simulated campaign).</p></div>') if history else ""

    style = _CSS
    script = ('function showMission(id){document.querySelectorAll(".mission")'
              '.forEach(function(e){e.style.display="none"});'
              'var el=document.getElementById(id); if(el) el.style.display="block";}')
    gen = html.escape(generated) if generated else ""
    doc = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>BrineWatch Digital Twin — {html.escape(site_name)}</title>
<style>{style}</style></head><body>
<header class="topbar" style="border-color:{b_color}">
  <div><h1>BrineWatch Digital Twin</h1>
    <p class="site">Site: {html.escape(site_name)}{(' · ' + gen) if gen else ''}</p>
    {f'<p class="sub2">{html.escape(subtitle)}</p>' if subtitle else ''}</div>
  <div class="banner" style="background:{b_bg};color:{b_color};border-color:{b_color}">
    <span class="banner-l">Latest screening</span>
    <span class="banner-v">{b_label}</span></div>
</header>
<main>
  <div class="card selector">
    <label for="msel"><strong>Mission</strong></label>
    <select id="msel" onchange="showMission(this.value)">{opts}</select>
    <span class="muted">{len(cards)} mission(s) on record</span>
  </div>
  {cards_html or '<div class="card"><p class="muted">No missions found.</p></div>'}
  {trends}
  <footer>Salinity field is the documented analytic <em>simulation surrogate</em>,
  not a CFD plume; ground-truth verdicts are evaluation-only. Generated by
  <code>brinewatch.visualization.dashboard</code>. Self-contained — no external
  assets, printable as a report.</footer>
</main>
<script>{script}</script>
</body></html>'''
    out_html.write_text(doc, encoding="utf-8")
    return out_html


_CSS = """
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
  background:#f4f6f8;color:#1f2937;line-height:1.5}
h1{font-size:1.5rem;margin:0}h2{font-size:1.15rem;margin:0 0 .6rem}
.topbar{display:flex;justify-content:space-between;align-items:center;gap:1rem;
  background:#fff;padding:1rem 1.5rem;border-bottom:4px solid;position:sticky;top:0;z-index:5}
.site{margin:.2rem 0 0;color:#6b7280;font-size:.9rem}
.sub2{margin:.15rem 0 0;color:#9ca3af;font-size:.82rem}
.banner{display:flex;flex-direction:column;align-items:center;border:2px solid;
  border-radius:12px;padding:.5rem 1.1rem;min-width:180px}
.banner-l{font-size:.7rem;letter-spacing:.06em;text-transform:uppercase;opacity:.8}
.banner-v{font-size:1.25rem;font-weight:700}
main{max-width:1080px;margin:1.2rem auto;padding:0 1rem;display:flex;flex-direction:column;gap:1.2rem}
.card{background:#fff;border-radius:14px;padding:1.1rem 1.3rem;
  box-shadow:0 1px 3px rgba(0,0,0,.08)}
.selector{display:flex;align-items:center;gap:.8rem}
select{font-size:.95rem;padding:.35rem .5rem;border-radius:8px;border:1px solid #d1d5db}
.card-head{display:flex;justify-content:space-between;align-items:flex-start;gap:1rem}
.sub{margin:.15rem 0 0;color:#6b7280;font-size:.85rem}
.badge{border:2px solid;border-radius:999px;padding:.3rem .8rem;font-weight:700;
  font-size:.85rem;white-space:nowrap}
.kpis{display:flex;flex-wrap:wrap;gap:.6rem;margin:1rem 0}
.kpi{background:#f8fafc;border:1px solid #eef2f7;border-radius:10px;padding:.55rem .8rem;
  min-width:120px;display:flex;flex-direction:column}
.kpi-v{font-size:1.15rem;font-weight:700;color:#111827}
.kpi-l{font-size:.72rem;color:#6b7280;text-transform:uppercase;letter-spacing:.03em}
.figs{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:1rem;margin-top:.6rem}
.mfig{margin:0}.mfig img{width:100%;border-radius:8px;border:1px solid #eef2f7}
.mfig figcaption{font-size:.8rem;color:#6b7280;margin-top:.3rem}
.charts{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:1rem}
.chart{margin:0;background:#fcfdff;border:1px solid #eef2f7;border-radius:10px;padding:.5rem}
.chart figcaption{font-size:.82rem;font-weight:600;margin-bottom:.2rem}
.chart svg{width:100%;height:auto}
.chart .tick,.chart .thr{font-size:9px;fill:#9ca3af}
.chart .axis{font-size:10px;fill:#6b7280}
.chart .tlnum{font-size:10px;fill:#fff;font-weight:700}
.grid{stroke:#eef2f7;stroke-width:1}
.notes{margin:.4rem 0 0;padding-left:1.1rem;color:#6b7280;font-size:.82rem}
.muted{color:#9ca3af;font-size:.85rem}
footer{color:#9ca3af;font-size:.78rem;padding:1rem .3rem 2rem;text-align:center}
"""

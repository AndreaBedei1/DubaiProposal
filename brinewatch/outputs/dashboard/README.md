# BrineWatch digital-twin dashboard (Phase 5)

A **single, self-contained HTML file** (`index.html`) — the digital record of the
site. Streamlit / Dash / plotly are not available in this environment, so the
dashboard is a static page: every mission figure is embedded as a base64 data
URI and every trend chart is inline SVG, so it opens in any browser with no
server and no external assets. It is therefore also the *exportable report* —
one file to archive or send.

Rebuild:

```bash
python scripts/build_dashboard.py            # auto-discovers committed missions
# or point it at specific runs / a history ledger:
python scripts/build_dashboard.py --mission outputs/custom_holoocean_mission_LATEST \
    --mission outputs/full_mission/custom_run1 \
    --history site_history/history.jsonl --out outputs/dashboard/index.html
```

## What it shows

- **Latest-screening banner** — CLEAR / REVIEW / POSSIBLE EXCEEDANCE, colour-coded,
  driving the header accent.
- **Mission selector** — switch between missions on record (vanilla-JS toggle;
  no framework).
- **Per-mission card** — the 2-D compliance/screening map, the ground-truth-vs-
  reconstruction map and (when present) the 3-D plume iso-surface + slices, plus
  KPI tiles: samples, budget, sonar localization error, reconstruction RMSE,
  boundary F1, plume volume, **collisions and minimum structure clearance**
  (collision-safe navigation), and the mission notes.
- **Site trends** — longitudinal charts across repeated missions from the
  site-history ledger: max anomaly outside the mixing zone (with the
  zero-anomaly threshold), worst-case exceedance probability (with the 0.5
  decision line), exceedance area, and a per-mission verdict timeline.
- **Honesty footer** — states that the salinity field is the analytic
  simulation surrogate and that ground-truth verdicts are evaluation-only.

## Files

| file | content |
|------|---------|
| `index.html` | the self-contained dashboard (open in any browser) |

Data sources are ordinary mission outputs: each mission's `summary.json`
(+ its figures) and a site-history `history.jsonl`. Loader + builder live in
`brinewatch/visualization/dashboard.py`; engine-free tests in
`tests/test_dashboard.py`.

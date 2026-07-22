"""Build the separate BrineWatch PFH 2026 technical evidence appendix."""
from __future__ import annotations

import argparse
from pathlib import Path

from reportlab.lib.colors import Color, HexColor
from reportlab.pdfgen import canvas

from build_public_competition_report import (
    BG, CORAL, CYAN, H, LINE, MUTED, PAGE, PANEL, PANEL_2, TEAL, W, WARM, WHITE,
    background, card, footer, paragraph, title,
)


ROOT = Path(__file__).resolve().parents[2]


def table(c, x, y, widths, row_h, headers, rows, *, font_size=8.2):
    total = sum(widths)
    c.setFillColor(PANEL_2)
    c.rect(x, y - row_h, total, row_h, stroke=0, fill=1)
    xx = x
    c.setFillColor(TEAL)
    c.setFont("Helvetica-Bold", font_size)
    for value, width in zip(headers, widths):
        c.drawString(xx + 6, y - row_h + 8, str(value))
        xx += width
    yy = y - row_h
    for idx, row in enumerate(rows):
        yy -= row_h
        c.setFillColor(PANEL if idx % 2 == 0 else BG)
        c.rect(x, yy, total, row_h, stroke=0, fill=1)
        xx = x
        c.setFillColor(WHITE if idx % 2 == 0 else MUTED)
        c.setFont("Helvetica", font_size)
        for value, width in zip(row, widths):
            c.drawString(xx + 6, yy + 8, str(value))
            xx += width
    c.setStrokeColor(LINE)
    c.rect(x, yy, total, y - yy, stroke=1, fill=0)
    xx = x
    for width in widths[:-1]:
        xx += width
        c.line(xx, yy, xx, y)
    return yy


def bullet_list(c, items, x, y, width, *, size=10, leading=14, accent=TEAL):
    for item in items:
        c.setFillColor(accent)
        c.circle(x + 3, y + 2, 2.5, stroke=0, fill=1)
        y = paragraph(c, item, x + 15, y + 6, width - 15, size=size,
                      leading=leading, color=WHITE) - 8
    return y


def page_scope(c):
    background(c)
    c.setFillColor(TEAL)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(46, H - 63, "BRINEWATCH / PFH 2026")
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 34)
    c.drawString(44, H - 118, "Technical evidence ledger")
    c.setFillColor(CYAN)
    c.setFont("Helvetica", 17)
    c.drawString(46, H - 151, "Metrics, assumptions, limitations and traceability")
    paragraph(c,
              "This appendix contains the technical detail intentionally removed from the public competition report.",
              46, H - 190, 680, size=13, leading=18, color=WHITE)

    evidence = [
        ("CUSTOM HOLOOCEAN", "vehicle + native sonar + safety", "not the reconstruction headline", TEAL),
        ("FLAGSHIP 2-D", "demo-optimised analytic surrogate", "not field or CFD truth", WARM),
        ("EQUAL-EVIDENCE TEST", "relative benchmark under fixed budget", "not universal superiority", CYAN),
        ("VOLUMETRIC MISSION", "one anisotropic 3-D GP", "not measured environmental volume", CORAL),
    ]
    for i, (label, support, limit, accent) in enumerate(evidence):
        y = 306 - i * 64
        card(c, 46, y, 750, 49, fill=PANEL, stroke=accent)
        c.setFillColor(accent)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(62, y + 30, label)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 10.5)
        c.drawString(245, y + 28, support)
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 9.5)
        c.drawString(535, y + 28, limit)
    c.setFillColor(WARM)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(46, 48, "STATUS: INITIAL PROTOTYPE OR MODEL  |  EVIDENCE FREEZE: 22 JULY 2026")
    footer(c, 1, "Evidence scope")
    c.showPage()


def page_engine(c):
    background(c)
    title(c, "01 / IN-ENGINE EVIDENCE", "Isolation, mission and localisation evidence")
    card(c, 42, 305, 365, 190, fill=PANEL_2, stroke=TEAL)
    c.setFillColor(TEAL)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(60, 468, "ISOLATION")
    bullet_list(c, [
        "Mission instance bwp26-fa3; cinematic instance bwp26-cin1.",
        "Private shared memory, semaphores, instance IDs, octrees, caches, temp, logs and outputs.",
        "Both manifests record launcher-owned engine PIDs and zero external process termination.",
    ], 60, 437, 325, size=9.5, leading=13)

    card(c, 430, 305, 368, 190, fill=PANEL_2, stroke=CYAN)
    c.setFillColor(CYAN)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(448, 468, "CUSTOM-HOLOOCEAN MISSION")
    bullet_list(c, [
        "564 simulated CT readings; 394.85 m travelled.",
        "0 collisions; 4 detours; 1.85 m minimum measured clearance vs 2.0 m target.",
        "REVIEW against non-compliant truth; RMSE 2.7203 PSU; F1 and IoU 0.000.",
        "Use as integration and safety evidence, not reconstruction evidence.",
    ], 448, 437, 327, size=9.5, leading=13, accent=CYAN)

    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(42, 268, "Forward-looking imaging-sonar localisation")
    metrics = [
        ("2.353 m", "centre error", TEAL),
        ("1.669 m", "posterior radius", CYAN),
        ("4.771 m", "confirmation spread", WARM),
        ("5 / 5", "valid non-fallback prior trials", CORAL),
    ]
    for i, (value, label, accent) in enumerate(metrics):
        x = 42 + i * 190
        card(c, x, 149, 177, 93, fill=PANEL, stroke=accent)
        c.setFillColor(accent)
        c.setFont("Helvetica-Bold", 20)
        c.drawString(x + 14, 205, value)
        paragraph(c, label, x + 14, 180, 145, size=9.5, leading=12, color=MUTED)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 9)
    c.drawString(42, 112, "Two independent search radii; inverse-uncertainty consensus; 5.0 m spread limit.")
    c.drawString(42, 96, "No oracle input and no silent fallback. Truth entered only after estimation for scoring.")
    footer(c, 2, "In-engine and localisation")
    c.showPage()


def page_screening(c):
    background(c)
    title(c, "02 / FLAGSHIP + SCREENING", "Flagship performance and all three screen states")
    metrics = [
        ("0.3415 PSU", "plume RMSE", TEAL),
        ("0.947", "boundary F1", CYAN),
        ("0.900", "boundary IoU", WARM),
        ("POSSIBLE EXCEEDANCE", "correct + conclusive", CORAL),
    ]
    for i, (value, label, accent) in enumerate(metrics):
        x = 42 + i * 190
        card(c, x, 387, 177, 95, fill=PANEL, stroke=accent)
        c.setFillColor(accent)
        c.setFont("Helvetica-Bold", 15 if i == 3 else 20)
        c.drawString(x + 13, 444, value)
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 9.5)
        c.drawString(x + 13, 414, label)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 9.2)
    c.drawString(42, 361,
        "Flagship: 591 samples; 516.55 / 520 m; coverage 0.770; P(exceed) 1.000; +1.234 PSU maximum reconstructed exceedance.")

    headers = ["Case", "Truth", "Output", "Samples", "P(exceed)", "RMSE", "F1"]
    rows = [
        ["Compliant reference", "PASS", "CLEAR", "1,049", "0.036", "0.0487", "1.000"],
        ["Borderline", "PASS", "REVIEW", "290", "0.363", "0.5749", "0.783"],
        ["Flagship", "FAIL", "POSSIBLE EXCEEDANCE", "591", "1.000", "0.3415", "0.947"],
    ]
    table(c, 42, 330, [158, 64, 160, 72, 83, 78, 65], 38, headers, rows, font_size=8.5)
    card(c, 42, 83, 752, 80, fill=PANEL_2, stroke=WARM)
    c.setFillColor(WARM)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(58, 137, "SCENARIO DISCLOSURE")
    paragraph(c,
        "The flagship intentionally uses a high-contrast analytic plume surrogate so the workflow is understandable. It preserves the accepted outfall geometry and is not field or CFD truth.",
        58, 114, 710, size=10, leading=14, color=WHITE)
    footer(c, 3, "Flagship and screen states")
    c.showPage()


def page_benchmark(c):
    background(c)
    title(c, "03 / EQUAL-EVIDENCE BENCHMARK", "Complete metric and screening table",
          "Eight seeds per method; 48 readings; 300 m cap; same area, analytic plume and 0.03 PSU sensor noise.")
    headers = ["Metric", "Sparse fixed", "Regular", "Adaptive"]
    rows = [
        ["Plume RMSE (PSU)", "1.151", "1.661", "0.758"],
        ["Boundary F1", "0.000", "0.287", "0.789"],
        ["Boundary IoU", "0.000", "0.177", "0.656"],
        ["Missed-plume fraction", "1.000", "0.817", "0.284"],
        ["Useful-sample fraction", "0.167", "0.229", "0.701"],
        ["Mean posterior std (PSU)", "2.169", "2.359", "2.292"],
        ["Max outside std (PSU)", "2.877", "4.500", "4.496"],
        ["Travel distance (m)", "297.8", "300.0", "297.5"],
        ["Indicative time (min)", "44.27", "9.93", "9.86"],
    ]
    y = table(c, 42, 445, [270, 160, 160, 160], 22, headers, rows, font_size=7.8)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(42, y - 30, "Screening counts")
    headers2 = ["Method", "CLEAR", "POSSIBLE", "REVIEW", "Conclusive", "Accuracy", "False C / E"]
    rows2 = [
        ["Sparse fixed", "0/8", "0/8", "8/8", "0%", "n/a", "0 / 0"],
        ["Regular", "0/8", "4/8", "4/8", "50%", "100%", "0 / 0"],
        ["Adaptive", "0/8", "8/8", "0/8", "100%", "100%", "0 / 0"],
        ["All", "0/24", "12/24", "12/24", "50%", "100%", "0 / 0"],
    ]
    table(c, 42, y - 45, [155, 80, 110, 80, 110, 100, 115], 22, headers2, rows2, font_size=7.5)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 8.5)
    c.drawString(42, 55,
        "Sparse design: 24 fixed stations plus one replicate each. REVIEW is not a miss, but it is not a conclusive detection; both rates remain visible.")
    footer(c, 4, "Complete benchmark")
    c.showPage()


def page_volume_cost(c):
    background(c)
    title(c, "04 / VOLUME + FEASIBILITY", "3-D evidence and planning assumptions")
    card(c, 42, 280, 365, 210, fill=PANEL_2, stroke=CORAL)
    c.setFillColor(CORAL)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(59, 461, "VOLUMETRIC MISSION")
    bullet_list(c, [
        "Four bands: 0.8, 1.6, 2.8 and 4.5 m; 912 total samples.",
        "One anisotropic 3-D GP; RMSE 0.477 PSU; MAE 0.238 PSU; volume IoU 0.805.",
        "2,051.3 m3 reconstructed vs 2,448.2 m3 surrogate truth: 16.2% underestimation.",
        "Uncertain volume 24,351.4 m3; mean std inside plume 1.551 PSU.",
    ], 59, 430, 325, size=9.3, leading=13, accent=CORAL)

    card(c, 430, 280, 368, 210, fill=PANEL_2, stroke=WARM)
    c.setFillColor(WARM)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(447, 461, "COST MODEL")
    bullet_list(c, [
        "Full build: USD 21.5k-44k.",
        "Incremental with owned ROV + sonar: USD 9k-22.5k.",
        "Survey day: shore USD 3.4k-8.9k; small boat USD 4.9k-13.4k.",
        "Midpoint break-even illustration: 2-7 repeats; not guaranteed.",
    ], 447, 430, 327, size=9.3, leading=13, accent=WARM)

    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(42, 244, "Assumptions and failure conditions")
    card(c, 42, 84, 756, 137, fill=PANEL, stroke=LINE)
    bullet_list(c, [
        "Two operators; 2.5-4 h on water; 4-8 h reporting; 12 missions/year; five-year amortisation.",
        "Public anchors at review: BlueROV2 from USD 4,900; Omniscan 450 FS from USD 2,490. Local CT, integration, vessel, labour and permits require quotes.",
        "If vessel, permits and accredited sampling remain unchanged, savings may disappear. The value becomes better spatial evidence and repeatable history.",
    ], 59, 189, 710, size=9.5, leading=13, accent=TEAL)
    footer(c, 5, "Volume and economics")
    c.showPage()


def page_limits(c):
    background(c)
    title(c, "05 / CLAIMS BOUNDARY", "What the evidence supports - and what it does not")
    card(c, 42, 258, 365, 235, fill=PANEL_2, stroke=TEAL)
    c.setFillColor(TEAL)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(59, 463, "SUPPORTED")
    bullet_list(c, [
        "Simulation-led prototype feasibility.",
        "Isolated collision-free custom-HoloOcean integration.",
        "Sonar localisation without oracle input.",
        "Uncertainty-aware three-state screening.",
        "Relative adaptive performance in the stated benchmark.",
        "Coherent 2-D / 3-D surrogate maps and digital-twin concept.",
    ], 59, 431, 325, size=9.5, leading=13, accent=TEAL)

    card(c, 430, 258, 368, 235, fill=PANEL_2, stroke=CORAL)
    c.setFillColor(CORAL)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(447, 463, "NOT SUPPORTED")
    bullet_list(c, [
        "Regulatory certification or autonomous compliance.",
        "Field accuracy or CFD validation.",
        "Guaranteed savings or break-even.",
        "Universal replacement of accredited monitoring.",
        "Unsupervised field deployment readiness.",
        "Measured environmental plume volume.",
    ], 447, 431, 327, size=9.5, leading=13, accent=CORAL)

    card(c, 42, 104, 756, 118, fill=PANEL, stroke=WARM)
    c.setFillColor(WARM)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(59, 192, "NEXT VALIDATION GATE")
    paragraph(c,
        "Integrate a calibrated conductivity-temperature payload, establish traceable timing and calibration, validate known gradients in controlled water, then run a supervised nearshore pilot with independent reference samples.",
        59, 166, 710, size=11.5, leading=16, color=WHITE)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 8.5)
    c.drawString(42, 72,
        "Video disclosure: 625 consecutive Full-HD HoloOcean frames; dedicated cinematic path, not a telemetry-synchronised replay; fixed scientific result panels.")
    footer(c, 6, "Limitations and next gate")
    c.showPage()


def build(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path), pagesize=PAGE, pageCompression=1)
    c.setTitle("BrineWatch PFH 2026 Technical Evidence Ledger")
    c.setAuthor("BrineWatch team")
    page_scope(c)
    page_engine(c)
    page_screening(c)
    page_benchmark(c)
    page_volume_cost(c)
    page_limits(c)
    c.save()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--out",
        default=str(ROOT / "output" / "pdf" / "BrineWatch_PFH2026_Technical_Evidence_Ledger.pdf"),
    )
    args = ap.parse_args()
    build(Path(args.out))
    print(Path(args.out).resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

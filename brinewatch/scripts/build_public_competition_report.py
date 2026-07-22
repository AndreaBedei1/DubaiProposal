"""Build the redesigned 10-page public BrineWatch competition report."""
from __future__ import annotations

import argparse
from pathlib import Path

from reportlab.lib.colors import Color, HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[2]
PAGE = landscape(A4)
W, H = PAGE
BG = HexColor("#06171d")
PANEL = HexColor("#0c2a33")
PANEL_2 = HexColor("#103844")
TEAL = HexColor("#2dd4bf")
CYAN = HexColor("#38bdf8")
WHITE = HexColor("#f4fbfc")
MUTED = HexColor("#a7c0c6")
WARM = HexColor("#fbbf24")
CORAL = HexColor("#fb7185")
LINE = HexColor("#1b4f5b")


def wrap(c, value, font, size, width):
    words = value.split()
    lines, current = [], ""
    for word in words:
        test = word if not current else f"{current} {word}"
        if c.stringWidth(test, font, size) <= width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def paragraph(c, value, x, y, width, *, size=12, leading=16, color=MUTED,
              font="Helvetica", max_lines=None):
    lines = wrap(c, value, font, size, width)
    if max_lines is not None:
        lines = lines[:max_lines]
    c.setFont(font, size)
    c.setFillColor(color)
    for line in lines:
        c.drawString(x, y, line)
        y -= leading
    return y


def background(c):
    c.setFillColor(BG)
    c.rect(0, 0, W, H, stroke=0, fill=1)


def footer(c, page_num, section):
    c.setStrokeColor(LINE)
    c.setLineWidth(.7)
    c.line(34, 25, W - 34, 25)
    c.setFont("Helvetica", 8)
    c.setFillColor(MUTED)
    c.drawString(34, 11, section.upper())
    c.drawRightString(W - 34, 11, f"BRINEWATCH / {page_num:02d}")


def title(c, kicker, headline, subhead=None):
    c.setFillColor(TEAL)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(40, H - 48, kicker.upper())
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 28)
    c.drawString(40, H - 80, headline)
    if subhead:
        paragraph(c, subhead, 40, H - 103, W - 80, size=11.5,
                  leading=14, color=MUTED)


def card(c, x, y, w, h, *, fill=PANEL, stroke=LINE, radius=10):
    c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.setLineWidth(.8)
    c.roundRect(x, y, w, h, radius, stroke=1, fill=1)


def image_size(path):
    image = ImageReader(str(path))
    return image, image.getSize()


def draw_contain(c, path, x, y, w, h, *, radius=None, bg=BG):
    image, (iw, ih) = image_size(path)
    scale = min(w / iw, h / ih)
    dw, dh = iw * scale, ih * scale
    dx, dy = x + (w - dw) / 2, y + (h - dh) / 2
    if radius:
        c.saveState()
        p = c.beginPath()
        p.roundRect(x, y, w, h, radius)
        c.clipPath(p, stroke=0, fill=0)
        c.setFillColor(bg)
        c.rect(x, y, w, h, stroke=0, fill=1)
        c.drawImage(image, dx, dy, dw, dh, preserveAspectRatio=True, mask="auto")
        c.restoreState()
    else:
        c.setFillColor(bg)
        c.rect(x, y, w, h, stroke=0, fill=1)
        c.drawImage(image, dx, dy, dw, dh, preserveAspectRatio=True, mask="auto")


def draw_cover(c, path, x=0, y=0, w=W, h=H):
    image, (iw, ih) = image_size(path)
    scale = max(w / iw, h / ih)
    dw, dh = iw * scale, ih * scale
    c.drawImage(image, x + (w - dw) / 2, y + (h - dh) / 2,
                dw, dh, preserveAspectRatio=True, mask="auto")


def pill(c, x, y, text, color=TEAL, width=None):
    c.setFont("Helvetica-Bold", 8)
    if width is None:
        width = c.stringWidth(text, "Helvetica-Bold", 8) + 22
    c.setFillColor(Color(color.red, color.green, color.blue, alpha=.18))
    c.setStrokeColor(color)
    c.roundRect(x, y, width, 22, 11, stroke=1, fill=1)
    c.setFillColor(color)
    c.drawCentredString(x + width / 2, y + 7.2, text)


def page_cover(c, assets, source_assets):
    draw_cover(c, source_assets / "hero_structure.png")
    c.setFillColor(Color(0.02, .09, .12, alpha=.86))
    c.rect(0, 0, 465, H, stroke=0, fill=1)
    c.setFillColor(Color(0.02, .09, .12, alpha=.36))
    c.rect(465, 0, W - 465, H, stroke=0, fill=1)

    c.setFillColor(TEAL)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(54, H - 70, "PROTOTYPES FOR HUMANITY 2026  |  INITIAL PROTOTYPE OR MODEL")
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 43)
    c.drawString(52, H - 155, "BRINEWATCH")
    c.setFillColor(CYAN)
    c.setFont("Helvetica", 23)
    c.drawString(54, H - 194, "See the plume. Target the evidence.")
    paragraph(
        c,
        "A repeatable underwater robot mission that maps desalination brine and guides certified follow-up sampling.",
        54, H - 245, 345, size=15, leading=21, color=WHITE,
    )
    c.setFillColor(Color(0.02, .09, .12, alpha=.80))
    c.roundRect(52, 64, 365, 61, 10, stroke=0, fill=1)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 10)
    c.drawString(70, 99, "BLUE ROV2  +  OMNISCAN 450 FS  +  PLANNED CT PAYLOAD")
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(70, 78, "From infrastructure inspection to environmental evidence")
    c.showPage()


def page_problem(c, assets):
    background(c)
    title(c, "01 / THE PROBLEM", "A few accurate readings can still miss the plume.",
          "Brine is released underwater. Operators need to understand its spatial extent, not only isolated values.")
    draw_contain(c, assets / "problem_simple.png", 36, 75, 535, 365, radius=12)

    card(c, 590, 240, 215, 200, fill=PANEL_2)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 17)
    c.drawString(610, 407, "Why this matters")
    bullets = [
        "The plume boundary can sit between fixed stations.",
        "Repeated vessel surveys take time and coordination.",
        "Certified samples are most useful when placed where uncertainty is highest.",
    ]
    y = 373
    for item in bullets:
        c.setFillColor(TEAL)
        c.circle(614, y + 2, 3.2, stroke=0, fill=1)
        y = paragraph(c, item, 628, y + 7, 155, size=10.5, leading=14,
                      color=WHITE, max_lines=3) - 14

    card(c, 590, 75, 215, 143, fill=Color(.06, .22, .27, alpha=1), stroke=TEAL)
    c.setFillColor(TEAL)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(610, 187, "THE GOAL")
    paragraph(c,
              "Find the outfall, map where the plume goes and tell operators where certified follow-up evidence is needed.",
              610, 160, 170, size=13, leading=18, color=WHITE)
    footer(c, 2, "Problem and impact")
    c.showPage()


def _draw_rov_system(c, x, y, w, h):
    card(c, x, y, w, h, fill=PANEL_2, stroke=LINE, radius=14)
    # ROV body and thrusters.
    c.setFillColor(HexColor("#d8e6e8"))
    c.roundRect(x + 60, y + 92, 160, 64, 12, stroke=0, fill=1)
    c.setFillColor(HexColor("#1a4652"))
    for tx in [x + 72, x + 190]:
        c.circle(tx, y + 90, 22, stroke=0, fill=1)
        c.circle(tx, y + 157, 22, stroke=0, fill=1)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(x + 140, y + 120, "BLUE ROV2")
    pill(c, x + 63, y + 55, "ALREADY OWNED", TEAL, 154)

    # Sonar beam and CT probe.
    c.setFillColor(Color(.22, .74, .97, alpha=.22))
    p = c.beginPath()
    p.moveTo(x + 220, y + 124)
    p.lineTo(x + 340, y + 178)
    p.lineTo(x + 340, y + 70)
    p.close()
    c.drawPath(p, stroke=0, fill=1)
    c.setStrokeColor(CYAN)
    c.line(x + 220, y + 124, x + 340, y + 178)
    c.line(x + 220, y + 124, x + 340, y + 70)
    c.setFillColor(CYAN)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x + 235, y + 183, "OMNISCAN 450 FS")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 9)
    c.drawString(x + 235, y + 168, "forward-looking imaging sonar")

    c.setStrokeColor(WARM)
    c.setLineWidth(3)
    c.line(x + 140, y + 92, x + 140, y + 27)
    c.setFillColor(WARM)
    c.circle(x + 140, y + 24, 7, stroke=0, fill=1)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x + 160, y + 26, "CALIBRATED CT PAYLOAD")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 9)
    c.drawString(x + 160, y + 11, "next integration step")

    # Outfall geometry reference.
    c.setStrokeColor(HexColor("#829aa0"))
    c.setLineWidth(8)
    c.line(x + 350, y + 70, x + 450, y + 70)
    for xx in [x + 370, x + 395, x + 420, x + 445]:
        c.setLineWidth(3)
        c.line(xx, y + 70, xx, y + 99)
    c.setFillColor(MUTED)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(x + 405, y + 45, "MULTIPORT OUTFALL")


def page_solution(c):
    background(c)
    title(c, "02 / THE SOLUTION", "One robot links infrastructure to environmental evidence.",
          "The same mission first finds the structure, then concentrates sensing where the water map needs it most.")
    _draw_rov_system(c, 43, 260, 755, 185)

    steps = [
        ("1", "LOCATE", "Confirm the diffuser from several sonar aspects."),
        ("2", "SENSE", "Measure salinity and temperature around the outfall."),
        ("3", "ADAPT", "Spend the route where information is most useful."),
        ("4", "RECONSTRUCT", "Turn samples into a map and uncertainty."),
        ("5", "ACT", "Guide certified follow-up to the locations that matter."),
    ]
    gap = 10
    cw = (W - 80 - gap * 4) / 5
    for i, (num, name, body) in enumerate(steps):
        x = 40 + i * (cw + gap)
        card(c, x, 73, cw, 158, fill=PANEL, stroke=TEAL if i < 4 else WARM)
        c.setFillColor(TEAL if i < 4 else WARM)
        c.circle(x + 21, 205, 12, stroke=0, fill=1)
        c.setFillColor(BG)
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(x + 21, 201.5, num)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(x + 14, 174, name)
        paragraph(c, body, x + 14, 148, cw - 28, size=9.5, leading=13,
                  color=MUTED, max_lines=4)
    footer(c, 3, "System and workflow")
    c.showPage()


def page_mission(c, assets):
    background(c)
    title(c, "03 / MISSION STORY", "The structure appears early - and stays understandable.",
          "Four genuine frames from one continuous custom-HoloOcean approach and inspection sequence.")
    frames = [
        ("mission_descent.jpg", "1  DESCEND", "The outfall is visible through moderate haze."),
        ("mission_approach.jpg", "2  APPROACH", "A smooth camera path preserves spatial continuity."),
        ("mission_inspection.jpg", "3  INSPECT", "The vehicle follows the main pipe and diffuser."),
        ("mission_diffuser.jpg", "4  SENSE", "Risers and nozzles define where sampling begins."),
    ]
    positions = [(42, 270), (430, 270), (42, 65), (430, 65)]
    for (name, label, caption), (x, y) in zip(frames, positions):
        draw_contain(c, assets / name, x, y + 37, 365, 170, radius=10)
        c.setFillColor(TEAL)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(x + 4, y + 18, label)
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 9.5)
        c.drawString(x + 86, y + 18, caption)
    footer(c, 4, "Genuine continuous HoloOcean sequence")
    c.showPage()


def page_twin(c, assets):
    background(c)
    title(c, "04 / DIGITAL TWIN", "The twin is the site's evolving memory.",
          "It combines what the robot saw, what it measured, what remains uncertain and what should happen next.")
    draw_contain(c, assets / "digital_twin_simple.png", 37, 78, 768, 432, radius=12)
    c.setFillColor(Color(.02, .09, .12, alpha=.92))
    c.roundRect(160, 52, 522, 36, 18, stroke=0, fill=1)
    c.setFillColor(WARM)
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(W / 2, 65, "An operational record - not a decorative 3-D model")
    footer(c, 5, "Digital twin explained simply")
    c.showPage()


def _result_card(c, image, x, y, w, h, label, metric, explanation, accent):
    card(c, x, y, w, h, fill=PANEL, stroke=accent, radius=12)
    draw_contain(c, image, x + 10, y + 55, w * .52, h - 68, radius=7)
    tx = x + w * .57
    c.setFillColor(accent)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(tx, y + h - 27, label.upper())
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(tx, y + h - 60, metric)
    paragraph(c, explanation, tx, y + h - 84, w * .38, size=9.5,
              leading=13, color=MUTED, max_lines=5)


def page_results(c, assets):
    background(c)
    title(c, "05 / WHAT ALREADY WORKS", "Four results answer four practical questions.",
          "The public story uses one evidence view per result. Full metrics and limitations remain in the technical ledger.")
    cards = [
        ("result_sonar.png", 41, 290, "FIND THE OUTFALL", "2.35 m",
         "Scored centre error from multi-radius sonar confirmation; no oracle input.", TEAL),
        ("result_mission.png", 430, 290, "MOVE SAFELY", "0 collisions",
         "395 m real in-engine route with 564 simulated CT readings.", CYAN),
        ("result_2d.png", 41, 75, "MAP THE BOUNDARY", "0.900 IoU",
         "Flagship 2-D reconstruction with a correct conclusive screen.", WARM),
        ("result_3d.png", 430, 75, "SEE THE VOLUME", "0.805 IoU",
         "One anisotropic 3-D GP updated across four altitude bands.", CORAL),
    ]
    for name, x, y, label, metric, explanation, accent in cards:
        _result_card(c, assets / name, x, y, 370, 185, label, metric, explanation, accent)

    c.setFillColor(Color(.06, .17, .20, alpha=1))
    c.roundRect(41, 45, 759, 22, 8, stroke=0, fill=1)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 8.5)
    c.drawCentredString(W / 2, 52.5,
        "Simulation evidence. The plume is an analytic surrogate; the flagship is demo-optimised, not field or CFD truth.")
    footer(c, 6, "Strongest validated simulation results")
    c.showPage()


def page_adaptive(c, assets):
    background(c)
    title(c, "06 / WHY ADAPT THE ROUTE", "Same evidence budget. Better use of each reading.",
          "The question is not who collects more data. It is who learns more from the same constrained mission.")
    draw_contain(c, assets / "adaptive_comparison_simple.png", 42, 62, 756, 407, radius=12)
    footer(c, 7, "Equal-evidence benchmark")
    c.showPage()


def page_feasibility(c):
    background(c)
    title(c, "07 / FEASIBILITY", "Reuse the robot. Add calibrated sensing.",
          "The core robotic platform and sonar are already owned. The next investment is sensor integration and validation.")

    card(c, 42, 337, 366, 125, fill=PANEL_2, stroke=TEAL)
    c.setFillColor(TEAL)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(61, 436, "ALREADY OWNED")
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(61, 405, "BlueROV2 + Omniscan 450 FS")
    paragraph(c, "Existing hardware lowers the next project gate and supports combined inspection and screening.",
              61, 381, 325, size=10, leading=14, color=MUTED)

    card(c, 430, 337, 368, 125, fill=PANEL_2, stroke=WARM)
    c.setFillColor(WARM)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(449, 436, "STILL REQUIRED")
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(449, 405, "Calibrated CT + integration + validation")
    paragraph(c, "Payload interface, calibration equipment, batteries/spares and independent reference sampling.",
              449, 381, 327, size=10, leading=14, color=MUTED)

    costs = [
        ("FULL NEW BUILD", "USD 21.5k - 44k", "ROV, sonar, CT, integration, compute and spares", CYAN),
        ("INCREMENTAL NEXT STEP", "USD 9k - 22.5k", "Given the already-owned ROV and sonar", TEAL),
        ("INDICATIVE SURVEY DAY", "USD 3.4k - 13.4k", "Shore to small-boat scenarios with targeted reference sampling", WARM),
    ]
    for i, (label, value, body, accent) in enumerate(costs):
        x = 42 + i * 252
        card(c, x, 193, 238, 118, fill=PANEL, stroke=accent)
        c.setFillColor(accent)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(x + 16, 282, label)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 19)
        c.drawString(x + 16, 250, value)
        paragraph(c, body, x + 16, 228, 205, size=9, leading=12, color=MUTED,
                  max_lines=3)

    # Deployment flow.
    flow = ["shore / small boat", "one robot mission", "same-day spatial map", "targeted certified samples"]
    for i, item in enumerate(flow):
        x = 50 + i * 190
        pill(c, x, 120, item.upper(), TEAL if i < 3 else WARM, 168)
        if i < 3:
            c.setStrokeColor(MUTED)
            c.setLineWidth(1.2)
            c.line(x + 171, 131, x + 186, 131)
            c.setFillColor(MUTED)
            p = c.beginPath()
            p.moveTo(x + 186, 131)
            p.lineTo(x + 180, 135)
            p.lineTo(x + 180, 127)
            p.close()
            c.drawPath(p, stroke=0, fill=1)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 8)
    c.drawString(42, 87,
        "Planning ranges, not quotations or guaranteed savings. Public anchors: Blue Robotics and Cerulean Sonar starting prices; local CT, vessel, labour and permits require quotes.")
    c.drawString(42, 73,
        "Value can remain even when accredited sampling is mandatory: less blind surveying, faster spatial evidence and repeatable site history.")
    footer(c, 8, "Technical and economic feasibility")
    c.showPage()


def page_roadmap(c):
    background(c)
    title(c, "08 / ROADMAP AND IMPACT", "Four gates turn a prototype into trusted field evidence.",
          "Autonomy expands only after calibration, independent reference measurements and supervised operating procedures.")
    stages = [
        ("0-3 MONTHS", "CT integration", "Traceable sensor stream", TEAL),
        ("3-6 MONTHS", "Controlled water", "Error bounds vs measured truth", CYAN),
        ("6-12 MONTHS", "Nearshore pilot", "Agreement + safe procedures", WARM),
        ("12-18 MONTHS", "Repeated campaigns", "Operational acceptance", CORAL),
    ]
    for i, (time, name, gate, accent) in enumerate(stages):
        x = 43 + i * 194
        card(c, x, 278, 179, 181, fill=PANEL, stroke=accent)
        c.setFillColor(accent)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(x + 14, 430, time)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(x + 14, 393, name)
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 9.5)
        c.drawString(x + 14, 331, "SUCCESS GATE")
        paragraph(c, gate, x + 14, 310, 150, size=10.5, leading=14, color=WHITE)
        if i < 3:
            c.setStrokeColor(MUTED)
            c.line(x + 182, 369, x + 191, 369)

    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 17)
    c.drawString(43, 237, "Who benefits")
    beneficiaries = [
        ("DESALINATION OPERATORS", "same-day spatial screening"),
        ("ENVIRONMENTAL TEAMS", "better targeted reference sampling"),
        ("MARINE ROBOTICS TEAMS", "one mission, two operational purposes"),
        ("RESEARCH + AUTHORITIES", "repeatable evidence and transparent uncertainty"),
    ]
    for i, (name, body) in enumerate(beneficiaries):
        x = 43 + i * 194
        card(c, x, 112, 179, 94, fill=PANEL_2, stroke=LINE)
        c.setFillColor(TEAL)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(x + 13, 179, name)
        paragraph(c, body, x + 13, 154, 150, size=10, leading=13,
                  color=WHITE, max_lines=3)
    c.setFillColor(WARM)
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(W / 2, 78,
        "Potential impact: more frequent screening, less blind surveying and a site history that improves over time.")
    footer(c, 9, "Deployment gates and beneficiaries")
    c.showPage()


def page_close(c, assets):
    draw_cover(c, assets / "mission_final.jpg")
    c.setFillColor(Color(.02, .09, .12, alpha=.78))
    c.rect(0, 0, W, H, stroke=0, fill=1)
    c.setFillColor(TEAL)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(54, H - 65, "BRINEWATCH  |  INITIAL PROTOTYPE OR MODEL")
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 31)
    c.drawString(52, H - 132, "From underwater inspection to")
    c.drawString(52, H - 171, "actionable environmental evidence.")

    card(c, 53, 210, 350, 150, fill=Color(.02, .10, .13, alpha=.92), stroke=TEAL)
    c.setFillColor(TEAL)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(72, 330, "WHAT ALREADY EXISTS")
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(72, 299, "Isolated in-engine mission")
    c.drawString(72, 274, "Sonar localisation")
    c.drawString(72, 249, "Adaptive 2-D + 3-D reconstruction")

    card(c, 430, 210, 359, 150, fill=Color(.02, .10, .13, alpha=.92), stroke=WARM)
    c.setFillColor(WARM)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(449, 330, "WHAT SUPPORT UNLOCKS")
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(449, 299, "Calibrated CT integration")
    c.drawString(449, 274, "Controlled-water validation")
    c.drawString(449, 249, "A supervised nearshore pilot")

    c.setFillColor(Color(.02, .09, .12, alpha=.92))
    c.roundRect(53, 91, 736, 74, 12, stroke=0, fill=1)
    c.setFillColor(WARM)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(72, 139, "NEXT CONCRETE STEP")
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(72, 108, "Calibrated CT integration and controlled-water validation.")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 8)
    c.drawString(54, 49,
        "Final status: simulation-led prototype. No field validation, regulatory certification or universal replacement claim.")
    c.showPage()


def build(out, assets, source_assets):
    out.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(out), pagesize=PAGE, pageCompression=1)
    c.setTitle("BrineWatch - PFH 2026 Public Competition Report")
    c.setAuthor("BrineWatch team")
    page_cover(c, assets, source_assets)
    page_problem(c, assets)
    page_solution(c)
    page_mission(c, assets)
    page_twin(c, assets)
    page_results(c, assets)
    page_adaptive(c, assets)
    page_feasibility(c)
    page_roadmap(c)
    page_close(c, assets)
    c.save()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--assets", default=str(ROOT / "output" / "redesign" / "assets"))
    ap.add_argument("--source-assets", default=str(ROOT / "output" / "fasttrack" / "assets"))
    ap.add_argument(
        "--out",
        default=str(ROOT / "output" / "pdf" / "BrineWatch_PFH2026_Public_Competition_Report.pdf"),
    )
    args = ap.parse_args()
    build(Path(args.out), Path(args.assets), Path(args.source_assets))
    print(Path(args.out).resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

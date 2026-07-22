"""Build the design-led BrineWatch PFH 2026 fast-track report."""
from __future__ import annotations

from pathlib import Path

from PIL import Image
from reportlab.lib.colors import Color, HexColor, white
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph, Table, TableStyle

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "output" / "fasttrack" / "assets"
VIDEO = ROOT / "output" / "fasttrack" / "video"
OUT = ROOT / "output" / "fasttrack" / "pdf"
TMP = ROOT / "tmp" / "pdfs" / "brinewatch_fasttrack"
PDF = OUT / "BrineWatch_PFH2026_FastTrack_Competition_Report.pdf"
PAGE = landscape(A4)
PW, PH = PAGE

NAVY = HexColor("#06171d")
PANEL = HexColor("#0b252d")
PANEL2 = HexColor("#10323b")
TEAL = HexColor("#2dd4bf")
CYAN = HexColor("#38bdf8")
AMBER = HexColor("#fbbf24")
RED = HexColor("#fb7185")
MUTED = HexColor("#9db7bc")
PALE = HexColor("#f4fbfc")
LINE = HexColor("#28515a")


def fonts():
    regular = Path("C:/Windows/Fonts/aptos.ttf")
    bold = Path("C:/Windows/Fonts/aptos-bold.ttf")
    if regular.exists() and bold.exists():
        pdfmetrics.registerFont(TTFont("BW", str(regular)))
        pdfmetrics.registerFont(TTFont("BW-Bold", str(bold)))
        return "BW", "BW-Bold"
    return "Helvetica", "Helvetica-Bold"


REG, BOLD = fonts()


def cached(path: Path) -> Path:
    """JPEG cache keeps the upload PDF compact while preserving layout."""
    TMP.mkdir(parents=True, exist_ok=True)
    target = TMP / f"{path.stem}.jpg"
    if not target.exists() or target.stat().st_mtime < path.stat().st_mtime:
        with Image.open(path) as im:
            im = im.convert("RGB")
            if max(im.size) > 2600:
                ratio = 2600 / max(im.size)
                im = im.resize((int(im.width * ratio), int(im.height * ratio)),
                               Image.Resampling.LANCZOS)
            im.save(target, "JPEG", quality=90, optimize=True, progressive=True)
    return target


def background(c: Canvas, page: int, section="BRINEWATCH"):
    c.setFillColor(NAVY)
    c.rect(0, 0, PW, PH, stroke=0, fill=1)
    c.setStrokeColor(LINE)
    c.setLineWidth(.5)
    c.line(34, 25, PW - 34, 25)
    c.setFillColor(MUTED)
    c.setFont(REG, 7.5)
    c.drawString(34, 12, section)
    c.drawRightString(PW - 34, 12, f"PFH 2026 / {page:02d}")


def heading(c: Canvas, kicker, title, subtitle=""):
    c.setFillColor(TEAL)
    c.setFont(BOLD, 9)
    c.drawString(40, PH - 45, kicker.upper())
    c.setFillColor(white)
    c.setFont(BOLD, 25)
    c.drawString(40, PH - 77, title)
    if subtitle:
        c.setFillColor(MUTED)
        c.setFont(REG, 10.5)
        c.drawString(40, PH - 97, subtitle)


def para(c, value, x, y_top, w, h, size=10, color=PALE, bold=False,
         leading=None):
    style = ParagraphStyle(
        "p", fontName=BOLD if bold else REG, fontSize=size,
        leading=leading or size * 1.32, textColor=color, alignment=TA_LEFT)
    p = Paragraph(value, style)
    _, ph = p.wrap(w, h)
    p.drawOn(c, x, y_top - ph)


def image(c, path, x, y, w, h, crop=False, radius=6):
    path = cached(Path(path))
    with Image.open(path) as im:
        iw, ih = im.size
    scale = max(w / iw, h / ih) if crop else min(w / iw, h / ih)
    sw, sh = iw * scale, ih * scale
    dx, dy = x + (w - sw) / 2, y + (h - sh) / 2
    c.saveState()
    if crop:
        p = c.beginPath()
        p.roundRect(x, y, w, h, radius)
        c.clipPath(p, stroke=0, fill=0)
    c.drawImage(ImageReader(str(path)), dx, dy, sw, sh,
                preserveAspectRatio=True, mask="auto")
    c.restoreState()


def box(c, x, y, w, h, label, value, note, accent=TEAL, value_size=18):
    c.setFillColor(PANEL2)
    c.roundRect(x, y, w, h, 7, stroke=0, fill=1)
    c.setStrokeColor(LINE)
    c.roundRect(x, y, w, h, 7, stroke=1, fill=0)
    c.setFillColor(MUTED)
    c.setFont(BOLD, 7)
    c.drawString(x + 12, y + h - 17, label.upper())
    c.setFillColor(accent)
    c.setFont(BOLD, value_size)
    c.drawString(x + 12, y + h - 43, value)
    c.setFillColor(MUTED)
    c.setFont(REG, 7.5)
    c.drawString(x + 12, y + 11, note)


def pill(c, x, y, value, accent=AMBER):
    c.setFont(BOLD, 7.5)
    w = c.stringWidth(value, BOLD, 7.5) + 18
    c.setFillColor(accent)
    c.roundRect(x, y, w, 18, 9, stroke=0, fill=1)
    c.setFillColor(NAVY)
    c.drawString(x + 9, y + 5, value)


def cover(c):
    image(c, ASSETS / "hero_structure.png", 0, 0, PW, PH, crop=True, radius=0)
    c.setFillColor(Color(0.02, .09, .11, alpha=.67))
    c.rect(0, 0, PW, PH, stroke=0, fill=1)
    c.setFillColor(Color(0.02, .09, .11, alpha=.88))
    c.roundRect(42, 53, 515, 265, 12, stroke=0, fill=1)
    c.setFillColor(TEAL)
    c.setFont(BOLD, 10)
    c.drawString(66, 287, "PROTOTYPES FOR HUMANITY 2026 / COMPETITION PACKAGE")
    c.setFillColor(white)
    c.setFont(BOLD, 43)
    c.drawString(64, 232, "BRINEWATCH")
    c.setFillColor(CYAN)
    c.setFont(REG, 18)
    c.drawString(66, 195, "See the plume. Target the evidence.")
    para(c,
         "An underwater monitoring prototype that combines forward-looking imaging sonar, CT sensing, adaptive sampling and an uncertainty-aware digital twin for desalination outfalls.",
         66, 166, 450, 72, 11.5)
    pill(c, 66, 71, "INITIAL PROTOTYPE OR MODEL")
    c.setFillColor(PALE)
    c.setFont(REG, 8)
    c.drawRightString(PW - 32, 24,
                      "Simulation-backed prototype / real custom-HoloOcean mission evidence")


def page_problem(c, n):
    background(c, n, "PROBLEM + VALUE")
    heading(c, "01 / problem", "Sparse measurements can miss the spatial boundary",
            "BrineWatch adds a repeatable screening layer before certified/manual sampling is deployed.")
    image(c, ASSETS / "hero_structure.png", 40, 70, 405, 395, crop=True)
    c.setFillColor(PANEL)
    c.roundRect(470, 285, 330, 180, 8, stroke=0, fill=1)
    para(c, "<b>Current monitoring limitation</b>", 490, 438, 290, 30,
         15, color=white, bold=True)
    para(c,
         "Fixed stations and limited CT casts can confirm conditions only where they were placed. A moving, bottom-hugging plume can remain spatially under-resolved, while a conventional spatial vessel survey can be costly to repeat.",
         490, 398, 285, 105, 10.5)
    c.setFillColor(PANEL)
    c.roundRect(470, 70, 330, 190, 8, stroke=0, fill=1)
    para(c, "<b>BrineWatch value</b>", 490, 232, 290, 30,
         15, color=white, bold=True)
    para(c,
         "More informative spatial evidence under constrained survey time - and a map that helps direct certified/manual sampling toward the locations that matter. The prototype does <b>not</b> claim to universally replace accredited monitoring.",
         490, 193, 285, 113, 10.5)
    pill(c, 490, 88, "SAME-DAY MAP", TEAL)
    pill(c, 595, 88, "TARGETED FOLLOW-UP", CYAN)
    pill(c, 715, 88, "SITE HISTORY", AMBER)


def page_system(c, n):
    background(c, n, "SYSTEM CONCEPT")
    heading(c, "02 / solution", "One mission links infrastructure to environmental evidence",
            "The planned payload is modular: owned BlueROV2 + owned Omniscan 450 FS + next-step CT integration.")
    steps = [
        ("1", "LOCATE", "Omniscan 450 FS", "Confirm the diffuser from several aspects."),
        ("2", "SENSE", "CT payload", "Sample salinity and temperature along the route."),
        ("3", "ADAPT", "Information gain", "Spend travel budget near signal and uncertainty."),
        ("4", "RECONSTRUCT", "2-D + 3-D GP", "Store the estimate and confidence, not only points."),
        ("5", "ACT", "Three-state screen", "CLEAR, REVIEW or POSSIBLE EXCEEDANCE."),
    ]
    for i, (num, title, sub, body) in enumerate(steps):
        x = 40 + i * 160
        c.setFillColor(PANEL)
        c.roundRect(x, 330, 143, 160, 8, stroke=0, fill=1)
        c.setFillColor(TEAL if i < 4 else AMBER)
        c.circle(x + 24, 461, 14, stroke=0, fill=1)
        c.setFillColor(NAVY)
        c.setFont(BOLD, 10)
        c.drawCentredString(x + 24, 457, num)
        c.setFillColor(white)
        c.setFont(BOLD, 11)
        c.drawString(x + 16, 420, title)
        para(c, f"<b>{sub}</b>", x + 16, 398, 112, 30, 8.2, color=CYAN)
        para(c, body, x + 16, 361, 112, 52, 7.7, color=MUTED)
    image(c, ASSETS / "digital_twin_dashboard.png", 40, 55, 760, 245)


def page_engine(c, n):
    background(c, n, "REAL IN-ENGINE EVIDENCE")
    heading(c, "03 / custom HoloOcean", "The ROV completed a collision-free in-engine mission",
            "The accepted outfall geometry was not redesigned. Vehicle motion and sonar are native simulation; the plume remains analytic.")
    image(c, VIDEO / "BrineWatch_PFH2026_Final_contact_sheet.jpg",
          40, 165, 760, 310)
    box(c, 42, 65, 135, 82, "CUSTOM ENGINE", "564", "CT samples", TEAL)
    box(c, 193, 65, 135, 82, "TRAVEL", "395 m", "in-engine route", CYAN)
    box(c, 344, 65, 135, 82, "SAFETY", "0", "collisions", TEAL)
    box(c, 495, 65, 135, 82, "CLEARANCE", "1.85 m", "measured minimum", AMBER)
    box(c, 646, 65, 154, 82, "SCREENING", "REVIEW", "honest abstention", AMBER, 15)
    para(c,
         "The 2.0 m standoff target was undershot by 0.15 m during dynamics but no collision occurred. This custom-engine run is locomotion/sensing evidence, not the headline reconstruction case.",
         42, 55, 758, 25, 7.4, color=MUTED)


def page_localization(c, n):
    background(c, n, "OMNISCAN 450 FS CONCEPT")
    heading(c, "04 / locate", "Multi-radius confirmation makes the sonar anchor defensible",
            "The planned and simulated sensing concept is consistently presented as forward-looking imaging sonar.")
    image(c, ASSETS / "sonar_localization.png", 38, 78, 766, 410)
    para(c,
         "Nominal two-radius inverse-uncertainty consensus: 2.35 m centre error, 1.67 m posterior radius and 334 deg aspect span. Five chart-prior perturbation fits remained non-fallback; their post-hoc median error was 4.24 m. No oracle coordinate entered localization.",
         45, 64, 750, 35, 7.8, color=MUTED)


def page_flagship(c, n):
    background(c, n, "FLAGSHIP DEMO")
    heading(c, "05 / 2-D result", "A clear plume supports a correct conclusive screen",
            "Demo-optimised high contrast is allowed for communication - and explicitly labelled as an analytic simulation surrogate.")
    image(c, ASSETS / "mission_reconstruction.png", 36, 65, 770, 430)
    para(c,
         "Flagship scenario: static tide, compact 60 m x 56 m site, 520 m budget and high salinity contrast. Result: 591 samples, 0.342 PSU plume RMSE, boundary F1 0.947, boundary IoU 0.899 and correct POSSIBLE EXCEEDANCE vs non-compliant surrogate truth.",
         44, 54, 755, 30, 7.6, color=MUTED)


def page_comparison(c, n):
    background(c, n, "EQUAL-BUDGET COMPARISON")
    heading(c, "06 / value evidence", "Same 48 readings. More informative spatial evidence.",
            "Eight seeds, same analytic plume, 300 m cap, mission area and CT noise for all three strategies.")
    image(c, ASSETS / "benchmark_comparison.png", 36, 72, 770, 420)
    rows = [
        ["Strategy", "CLEAR", "POSSIBLE", "REVIEW", "Conclusive", "Accuracy if conclusive"],
        ["Sparse fixed", "0 / 8", "0 / 8", "8 / 8", "0%", "n/a"],
        ["Lawnmower", "0 / 8", "4 / 8", "4 / 8", "50%", "100%"],
        ["BrineWatch adaptive", "0 / 8", "8 / 8", "0 / 8", "100%", "100%"],
    ]
    table = Table(rows, colWidths=[170, 80, 90, 80, 90, 130], rowHeights=[20] * 4)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TEAL),
        ("TEXTCOLOR", (0, 0), (-1, 0), NAVY),
        ("FONTNAME", (0, 0), (-1, 0), BOLD),
        ("BACKGROUND", (0, 1), (-1, -1), PANEL),
        ("TEXTCOLOR", (0, 1), (-1, -1), PALE),
        ("FONTNAME", (0, 1), (-1, -1), REG),
        ("FONTSIZE", (0, 0), (-1, -1), 7.6),
        ("GRID", (0, 0), (-1, -1), .4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
    ]))
    table.wrapOn(c, 650, 80)
    table.drawOn(c, 96, 43)


def page_3d(c, n):
    background(c, n, "VOLUMETRIC RECONSTRUCTION")
    heading(c, "07 / 3-D result", "Four altitude bands reveal the plume as a volume",
            "One coherent anisotropic GP connects samples, trajectory, reconstructed isohaline and confidence bounds.")
    image(c, ASSETS / "plume_3d.png", 34, 68, 772, 430)
    para(c,
         "912 samples across 0.8, 1.6, 2.8 and 4.5 m bands. 3-D RMSE 0.477 PSU; volume IoU 0.805. Estimated volume 2,051 m3 vs 2,448 m3 surrogate truth - 16.2% under-estimation, replacing the previous over-estimation rather than hiding it.",
         44, 55, 754, 31, 7.6, color=MUTED)


def page_screening(c, n):
    background(c, n, "SCREENING HONESTY")
    heading(c, "08 / three states", "Conclusive when supported. REVIEW when it is not.",
            "Competition results remain persuasive because limitations and abstentions stay visible.")
    cases = [
        ("CLEAR", "Correct vs compliant truth", "1,049 samples | P(exceed) 0.036 | p95 std 0.83 PSU", TEAL),
        ("REVIEW", "Genuinely borderline", "290 samples | P(exceed) 0.363 | inconclusive vs compliant truth", AMBER),
        ("POSSIBLE EXCEEDANCE", "Correct vs non-compliant truth", "591 samples | P(exceed) 1.00 | +1.234 PSU maximum exceedance", RED),
    ]
    for i, (state, outcome, details, accent) in enumerate(cases):
        x = 42 + i * 254
        c.setFillColor(PANEL2)
        c.roundRect(x, 315, 234, 150, 8, stroke=0, fill=1)
        c.setFillColor(accent)
        c.setFont(BOLD, 14 if i < 2 else 11)
        c.drawString(x + 16, 425, state)
        para(c, f"<b>{outcome}</b>", x + 16, 395, 200, 30, 9.2, color=white)
        para(c, details, x + 16, 357, 200, 45, 8.2, color=MUTED)
    c.setFillColor(PANEL)
    c.roundRect(42, 92, 470, 185, 8, stroke=0, fill=1)
    para(c, "<b>What the benchmark reports</b>", 60, 250, 430, 28,
         14, color=white)
    para(c,
         "Counts and percentages for CLEAR, POSSIBLE EXCEEDANCE and REVIEW; conclusive rate; accuracy among conclusive outputs; false CLEAR; false exceedance; and abstention rate. In the 24-run direct comparison there were zero false CLEAR and zero false exceedance outputs.",
         60, 210, 425, 105, 10)
    c.setFillColor(PANEL)
    c.roundRect(532, 92, 268, 185, 8, stroke=0, fill=1)
    para(c, "<b>Stress evidence kept</b>", 550, 250, 230, 28,
         14, color=white)
    para(c,
         "The real custom-HoloOcean survey remained REVIEW and reconstructed the difficult field poorly (RMSE 2.72 PSU; boundary F1 0.00). It supports vehicle/sensor integration and safety - not the scientific headline.",
         550, 210, 225, 108, 9.5, color=AMBER)
    pill(c, 42, 58, "NO CERTIFICATION CLAIM", RED)
    pill(c, 177, 58, "NO CFD CLAIM", AMBER)
    pill(c, 268, 58, "NO UNIVERSAL REPLACEMENT CLAIM", CYAN)


def page_twin(c, n):
    background(c, n, "DIGITAL TWIN")
    heading(c, "09 / operational picture", "The twin is a mission history, not decorative 3-D",
            "A non-expert reviewer can see what changed, how certain it is and what action follows.")
    image(c, ASSETS / "digital_twin_dashboard.png", 35, 74, 772, 420)
    para(c,
         "Stored together: latest site map, 3-D plume estimate, uncertainty, ROV trajectory, sonar localization, screening result, previous missions and the recommended follow-up. This is currently simulation-based and not yet connected to a field data service.",
         44, 56, 754, 32, 7.6, color=MUTED)


def page_feasibility(c, n):
    background(c, n, "TECHNICAL + ECONOMIC FEASIBILITY")
    heading(c, "10 / cost model", "Reuse existing hardware to lower the next gate",
            "Ranges are transparent planning assumptions, not vendor quotations or guaranteed savings.")
    image(c, ASSETS / "feasibility_cost.png", 35, 73, 772, 420)
    para(c,
         "Public anchors: BlueROV2 base from USD 4,900 (Blue Robotics); Omniscan 450 FS from USD 2,490 (Cerulean Sonar); miniCT-class capability from Teledyne Valeport. CT price, vessel, permits and local labour require quotations. Sources accessed 22 Jul 2026.",
         44, 56, 754, 30, 7.1, color=MUTED)


def page_deployment(c, n):
    background(c, n, "DEPLOYMENT + ROADMAP")
    heading(c, "11 / from prototype to water", "Four gates turn a simulation result into field evidence",
            "Autonomy expands only after calibrated truth and supervised operating procedures.")
    phases = [
        ("0-3 MONTHS", "CT integration", "Mount, power, RS232/RS485 interface, time sync, calibration fixture.", "Gate: traceable sensor stream"),
        ("3-6 MONTHS", "Controlled water", "Known salinity gradients, repeated sonar geometry and mapping runs.", "Gate: error bounds vs measured truth"),
        ("6-12 MONTHS", "Nearshore pilot", "Permitted, supervised trials with independent reference samples.", "Gate: agreement + safe SOP"),
        ("12-18 MONTHS", "Repeated campaign", "Site history, operator handover, maintenance and unit economics.", "Gate: operational acceptance"),
    ]
    for i, (time, title, body, gate) in enumerate(phases):
        x = 42 + i * 190
        c.setFillColor(PANEL)
        c.roundRect(x, 286, 174, 198, 8, stroke=0, fill=1)
        c.setFillColor(TEAL if i < 2 else AMBER)
        c.setFont(BOLD, 8)
        c.drawString(x + 15, 457, time)
        c.setFillColor(white)
        c.setFont(BOLD, 13)
        c.drawString(x + 15, 423, title)
        para(c, body, x + 15, 395, 144, 76, 8.8)
        para(c, f"<b>{gate}</b>", x + 15, 321, 144, 42, 8.2, color=CYAN)
    risks = [
        ("Simulation-to-water gap", "tank truth + independent reference sampling"),
        ("Surrogate plume physics", "measured currents, calibrated transport model, later CFD coupling"),
        ("Sonar ambiguity", "multi-pass confirmation and REVIEW on disagreement"),
        ("Tether and navigation", "human abort, geofence, standoff and launch plan"),
    ]
    c.setFillColor(PANEL2)
    c.roundRect(42, 65, 760, 180, 8, stroke=0, fill=1)
    para(c, "<b>Principal risks and mitigations</b>", 60, 220, 720, 28,
         14, color=white)
    for i, (risk, mitigation) in enumerate(risks):
        x = 60 + (i % 2) * 365
        y = 175 - (i // 2) * 63
        c.setFillColor(RED)
        c.circle(x + 5, y + 4, 3, stroke=0, fill=1)
        para(c, f"<b>{risk}</b><br/>{mitigation}", x + 16, y + 18,
             320, 50, 8.7)


def close(c, n):
    image(c, ASSETS / "hero_structure.png", 0, 0, PW, PH, crop=True, radius=0)
    c.setFillColor(Color(0.02, .09, .11, alpha=.82))
    c.rect(0, 0, PW, PH, stroke=0, fill=1)
    c.setFillColor(white)
    c.setFont(BOLD, 31)
    c.drawString(44, PH - 64, "A convincing prototype with a precise next gate")
    c.setFillColor(CYAN)
    c.setFont(REG, 14)
    c.drawString(45, PH - 90,
                 "Integrate the CT payload. Validate in controlled water. Then target certified sampling.")
    box(c, 44, 300, 172, 105, "LOCALIZATION", "2.35 m", "multi-radius centre error", TEAL)
    box(c, 232, 300, 172, 105, "IN-ENGINE", "0", "collisions over 395 m", TEAL)
    box(c, 420, 300, 172, 105, "FLAGSHIP 2-D", "0.342", "PSU plume RMSE", CYAN)
    box(c, 608, 300, 172, 105, "VOLUME", "0.81", "3-D IoU", AMBER)
    c.setFillColor(PANEL)
    c.roundRect(44, 112, 500, 145, 8, stroke=0, fill=1)
    para(c, "<b>What support unlocks</b>", 62, 232, 460, 28,
         14, color=white)
    para(c,
         "A calibrated CT integration, controlled-water truth campaign and first supervised nearshore pilot. The team already brings the BlueROV2, Omniscan 450 FS, custom HoloOcean scene, mission software, strong demo outputs and a transparent evidence ledger.",
         62, 195, 455, 90, 10.4)
    c.setFillColor(PANEL)
    c.roundRect(565, 112, 215, 145, 8, stroke=0, fill=1)
    para(c, "<b>One-line value</b>", 582, 232, 180, 25, 12, color=white)
    para(c,
         "More informative spatial evidence under constrained survey time - so certified sampling can go where it matters.",
         582, 194, 178, 84, 10, color=TEAL, bold=True)
    c.setFillColor(AMBER)
    c.setFont(BOLD, 9)
    c.drawString(44, 78, "STATUS: INITIAL PROTOTYPE OR MODEL")
    c.setFillColor(PALE)
    c.setFont(REG, 8)
    c.drawString(44, 60,
                 "All performance values are simulation results. BrineWatch is not field validated or certified for regulatory compliance.")


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    c = Canvas(str(PDF), pagesize=PAGE, pageCompression=1)
    c.setTitle("BrineWatch PFH 2026 Fast-Track Competition Report")
    c.setAuthor("BrineWatch team")
    cover(c)
    c.showPage()
    pages = [page_problem, page_system, page_engine, page_localization,
             page_flagship, page_comparison, page_3d, page_screening,
             page_twin, page_feasibility, page_deployment, close]
    for number, fn in enumerate(pages, start=2):
        fn(c, number)
        c.showPage()
    c.save()
    print(PDF)


if __name__ == "__main__":
    build()

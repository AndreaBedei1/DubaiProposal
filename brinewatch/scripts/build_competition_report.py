"""Build the landscape competition report in output/pdf.

The report is deliberately presentation-led.  It uses only genuine simulator
captures and figures generated from recorded repository outputs.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from reportlab.lib.colors import Color, HexColor, white
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph, Table, TableStyle


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "output" / "pdf"
ASSETS = ROOT / "output" / "submission"
PDF = OUT / "BrineWatch_PFH2026_Competition_Report.pdf"
PAGE = landscape(A4)
PW, PH = PAGE

NAVY = HexColor("#071c27")
PANEL = HexColor("#0d3340")
PANEL2 = HexColor("#124554")
TEAL = HexColor("#19c3b1")
CYAN = HexColor("#5be7de")
SAND = HexColor("#f1c27d")
CORAL = HexColor("#ff7b6b")
MUTED = HexColor("#9fc1c6")
PALE = HexColor("#e8f4f2")
LINE = HexColor("#315663")


def register_fonts() -> tuple[str, str]:
    regular = Path("C:/Windows/Fonts/aptos.ttf")
    bold = Path("C:/Windows/Fonts/aptos-bold.ttf")
    if regular.exists() and bold.exists():
        pdfmetrics.registerFont(TTFont("BW", str(regular)))
        pdfmetrics.registerFont(TTFont("BW-Bold", str(bold)))
        return "BW", "BW-Bold"
    return "Helvetica", "Helvetica-Bold"


REG, BOLD = register_fonts()


def bg(c: Canvas, page: int, section: str = "BRINEWATCH") -> None:
    c.setFillColor(NAVY); c.rect(0, 0, PW, PH, stroke=0, fill=1)
    c.setStrokeColor(LINE); c.setLineWidth(.5); c.line(34, 25, PW-34, 25)
    c.setFillColor(MUTED); c.setFont(REG, 7.5); c.drawString(34, 12, section)
    c.drawRightString(PW-34, 12, f"PFH 2026  /  {page:02d}")


def title(c: Canvas, kicker: str, heading: str, subtitle: str = "") -> None:
    c.setFillColor(TEAL); c.setFont(BOLD, 9); c.drawString(40, PH-46, kicker.upper())
    c.setFillColor(white); c.setFont(BOLD, 26); c.drawString(40, PH-79, heading)
    if subtitle:
        c.setFillColor(MUTED); c.setFont(REG, 11); c.drawString(40, PH-99, subtitle)


def paragraph(c: Canvas, text: str, x: float, y_top: float, w: float, h: float,
              size: float = 10.5, color=PALE, leading: float | None = None, bold: bool = False) -> None:
    style = ParagraphStyle("body", fontName=BOLD if bold else REG, fontSize=size,
                           leading=leading or size*1.35, textColor=color, alignment=TA_LEFT,
                           spaceAfter=0)
    p = Paragraph(text, style); _, ph = p.wrap(w, h); p.drawOn(c, x, y_top-ph)


def fit_image(c: Canvas, path: Path, x: float, y: float, w: float, h: float,
              crop: bool = False, radius: float = 0) -> None:
    with Image.open(path) as im:
        iw, ih = im.size
    if crop:
        scale = max(w/iw, h/ih); sw, sh = iw*scale, ih*scale
    else:
        scale = min(w/iw, h/ih); sw, sh = iw*scale, ih*scale
    dx, dy = x+(w-sw)/2, y+(h-sh)/2
    c.saveState()
    if crop:
        p=c.beginPath(); p.roundRect(x,y,w,h,radius or 6); c.clipPath(p,stroke=0,fill=0)
    c.drawImage(ImageReader(str(path)), dx, dy, width=sw, height=sh, preserveAspectRatio=True, mask='auto')
    c.restoreState()


def card(c: Canvas, x: float, y: float, w: float, h: float, label: str, value: str,
         note: str, accent=TEAL) -> None:
    c.setFillColor(PANEL); c.roundRect(x,y,w,h,7,stroke=0,fill=1)
    c.setStrokeColor(LINE); c.roundRect(x,y,w,h,7,stroke=1,fill=0)
    c.setFillColor(MUTED); c.setFont(BOLD,7.5); c.drawString(x+12,y+h-17,label.upper())
    c.setFillColor(accent); c.setFont(BOLD,20); c.drawString(x+12,y+h-44,value)
    c.setFillColor(PALE); c.setFont(REG,8); c.drawString(x+12,y+12,note)


def pill(c: Canvas, x: float, y: float, text: str, color=TEAL) -> None:
    c.setFont(BOLD, 7.5); width=c.stringWidth(text,BOLD,7.5)+18
    c.setFillColor(color); c.roundRect(x,y,width,18,9,stroke=0,fill=1)
    c.setFillColor(NAVY); c.drawString(x+9,y+5,text)


def page_cover(c: Canvas) -> None:
    hero=ASSETS/"images/hero_structure.png"
    fit_image(c,hero,0,0,PW,PH,crop=True)
    c.setFillColor(Color(0.015,.08,.11,alpha=.66)); c.rect(0,0,PW,PH,stroke=0,fill=1)
    c.setFillColor(Color(0.015,.08,.11,alpha=.80)); c.roundRect(42,45,480,250,12,stroke=0,fill=1)
    c.setFillColor(TEAL); c.setFont(BOLD,10); c.drawString(66,267,"PROTOTYPES FOR HUMANITY  /  COMPETITION PACKAGE")
    c.setFillColor(white); c.setFont(BOLD,43); c.drawString(64,214,"BRINEWATCH")
    c.setFillColor(CYAN); c.setFont(REG,18); c.drawString(66,178,"Autonomous intelligence for desalination outfalls")
    paragraph(c,"A simulation-backed underwater monitoring prototype that locates diffuser infrastructure by sonar, maps salinity with adaptive sampling and turns each mission into an uncertainty-aware digital twin.",66,150,415,75,11.5)
    pill(c,66,67,"INITIAL PROTOTYPE OR MODEL",SAND)
    c.setFillColor(PALE); c.setFont(REG,8); c.drawRightString(PW-35,24,"Genuine HoloOcean RGB capture  |  July 2026")


def page_problem(c: Canvas, n: int) -> None:
    bg(c,n,"WHY BRINEWATCH")
    title(c,"01 / problem","A high-consequence blind spot below the surface","Monitoring must be spatial, repeatable and useful to an operator - not only a single bottle sample.")
    fit_image(c,ASSETS/"images/hero_structure_wide.png",40,60,430,360,crop=True,radius=7)
    c.setFillColor(PANEL); c.roundRect(495,250,307,170,8,stroke=0,fill=1)
    paragraph(c,"<b>The operational gap</b>",515,397,267,28,15,color=white,bold=True)
    paragraph(c,"Desalination outfalls are submerged, visibility varies and plume shape can change with discharge and ambient conditions. A fixed sensor or sparse manual transect can miss the spatial boundary that matters.",515,363,260,96,10.5)
    c.setFillColor(PANEL); c.roundRect(495,60,307,170,8,stroke=0,fill=1)
    paragraph(c,"<b>Our position</b>",515,207,267,28,15,color=white,bold=True)
    paragraph(c,"BrineWatch is a rapid screening and mission-planning layer. It is designed to prioritize where to sample, preserve uncertainty and create a traceable site history. It does not claim to replace certified compliance sampling.",515,173,260,96,10.5)
    pill(c,57,76,"VISIBLE STRUCTURE",TEAL); pill(c,175,76,"MURKY-WATER READY",SAND); pill(c,320,76,"REPEATABLE MISSIONS",CYAN)


def page_solution(c: Canvas, n: int) -> None:
    bg(c,n,"SYSTEM CONCEPT")
    title(c,"02 / solution","One mission, five connected decisions","The digital twin is not a static 3-D model: it is the evidence state updated after every measurement.")
    steps=[
        ("1","LOCATE","Sonar ring around a chart prior","Find the diffuser without oracle position."),
        ("2","BASELINE","Safe initial transects","Establish background and broad plume shape."),
        ("3","ADAPT","Sample boundaries and uncertainty","Trade travel distance for useful information."),
        ("4","RECONSTRUCT","2-D + 3-D salinity field","Update estimate, variance and site history."),
        ("5","SCREEN","CLEAR / REVIEW / POSSIBLE","Escalate uncertainty instead of hiding it."),
    ]
    y=365
    for i,(num,head,sub,desc) in enumerate(steps):
        x=42+i*159
        c.setFillColor(PANEL); c.roundRect(x,y,142,128,8,stroke=0,fill=1)
        c.setFillColor(TEAL if i<4 else SAND); c.circle(x+21,y+105,13,stroke=0,fill=1)
        c.setFillColor(NAVY); c.setFont(BOLD,10); c.drawCentredString(x+21,y+101,num)
        c.setFillColor(white); c.setFont(BOLD,11); c.drawString(x+16,y+76,head)
        paragraph(c,sub,x+16,y+62,111,35,8.5,color=CYAN,bold=True)
        paragraph(c,desc,x+16,y+28,111,33,7.6,color=MUTED)
        if i<4:
            c.setStrokeColor(LINE); c.setLineWidth(2); c.line(x+142,y+64,x+159,y+64)
    fit_image(c,ASSETS/"figures/digital_twin_dashboard.png",42,46,760,285,crop=False)


def page_engine(c: Canvas, n: int) -> None:
    bg(c,n,"PROTOTYPE EVIDENCE")
    title(c,"03 / in-engine mission","The full loop runs inside custom HoloOcean","Accepted outfall geometry, native simulated sonar, collision-safe vehicle motion and sensor sampling.")
    fit_image(c,ASSETS/"figures/sonar_localization.png",36,164,770,306,crop=False)
    cards=[
        ("LOCALIZATION","1.65 m","centre error",TEAL),
        ("MISSION","220 m","travel budget",CYAN),
        ("SAMPLING","271","CT samples",TEAL),
        ("SAFETY","0","collisions",TEAL),
        ("CLEARANCE","3.49 m","minimum",SAND),
    ]
    for i,args in enumerate(cards): card(c,42+i*153,66,139,86,*args)
    paragraph(c,"The localizer used 47 residual contacts from 16 viewpoints with no ground-truth position input. The scene contained 105 spawned outfall components and the survey triggered two safe detours.",42,55,760,28,7.8,color=MUTED)


def page_mapping(c: Canvas, n: int) -> None:
    bg(c,n,"MISSION RESULT")
    title(c,"04 / adaptive mapping","Map concentration and uncertainty together","The result is operationally useful only when the system also shows where it does not know enough.")
    fit_image(c,ASSETS/"figures/mission_reconstruction.png",40,155,762,345,crop=False)
    c.setFillColor(PANEL); c.roundRect(42,55,238,78,7,stroke=0,fill=1)
    paragraph(c,"<b>Result</b><br/>Boundary F1 = 0.686; plume RMSE = 2.45 PSU for this custom-engine mission.",56,117,210,53,8.5)
    c.setFillColor(PANEL); c.roundRect(296,55,238,78,7,stroke=0,fill=1)
    paragraph(c,"<b>Verdict</b><br/>REVIEW vs ground-truth PASS: conservative and inconclusive, not a claimed correct classification.",310,117,210,53,8.5,color=SAND)
    c.setFillColor(PANEL); c.roundRect(550,55,252,78,7,stroke=0,fill=1)
    paragraph(c,"<b>Why it matters</b><br/>The dashboard preserves uncertainty so an operator can commission a follow-up pass instead of receiving false certainty.",564,117,224,53,8.5)


def page_3d(c: Canvas, n: int) -> None:
    bg(c,n,"VOLUMETRIC TWIN")
    title(c,"05 / 3-D representation","See how the plume occupies the water column","Three sampling altitudes turn a flat map into a volumetric planning layer.")
    fit_image(c,ASSETS/"figures/plume_3d.png",37,70,770,420,crop=False)
    c.setFillColor(SAND); c.setFont(BOLD,7.5); c.drawString(45,51,"EVIDENCE BOUNDARY")
    c.setFillColor(MUTED); c.setFont(REG,7.5); c.drawString(135,51,"Analytic simulation surrogate; not CFD and not field ground truth. Estimated volume is 5,477 m3 vs 3,756 m3 truth (over-estimation is visible, not hidden).")


def page_benchmark(c: Canvas, n: int) -> None:
    bg(c,n,"VALIDATION")
    title(c,"06 / benchmark","Adaptive sampling wins where it should","Its value is strongest under time pressure - not as a universal replacement for dense coverage.")
    fit_image(c,ASSETS/"figures/benchmark_efficiency.png",42,180,760,294,crop=False)
    card(c,42,78,170,90,"DYNAMIC / 50% BUDGET","18.7%","lower plume RMSE",TEAL)
    card(c,228,78,170,90,"DYNAMIC / 50% BUDGET","+14.2%","relative boundary F1",CYAN)
    card(c,414,78,170,90,"SCREENING / 192 EVALS","0","wrong conclusive outputs",TEAL)
    card(c,600,78,202,90,"FULL COVERAGE","LAWNMOWER","is stronger; retained honestly",SAND)
    paragraph(c,"12 held-out seeds x 2 scenario families x 2 planners x 4 equal-budget checkpoints = 192 evaluations. REVIEW is treated as inconclusive, not correct.",42,66,760,25,7.8,color=MUTED)


def page_feasibility(c: Canvas, n: int) -> None:
    bg(c,n,"TECHNICAL FEASIBILITY")
    title(c,"07 / feasibility","A credible path from simulator to water","The core platform and sonar are already owned; the next gating item is a calibrated CT payload.")
    rows=[
        ["Subsystem","Role","Indicative USD","Status / assumption"],
        ["BlueROV2 + control + tether","vehicle and live operator link","4,900 - 8,000","base price verified; exact options vary"],
        ["Imaging / side-scan sonar","outfall acquisition","2,550 - 5,440","vendor options; sonar already owned"],
        ["Calibrated CT payload","salinity + temperature","1,500 - 6,000","planning allowance; vendor quote required"],
        ["Skid, enclosure, interface","mechanical/electrical integration","750 - 2,000","includes payload fixture and wet-mate items"],
        ["Batteries, spares, compute","mission endurance + topside","1,850 - 4,000","one spare-battery cycle and laptop class"],
        ["Commissioning + first field days","calibration, vessel, permits","2,000 - 6,000","site dependent; excludes long campaign"],
        ["NEW-BUILD PROGRAM RANGE","complete prototype replacement","13,550 - 31,440","planning range, not a supplier quotation"],
    ]
    table=Table(rows,colWidths=[170,200,115,250],rowHeights=[28]+[34]*7)
    table.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),TEAL),('TEXTCOLOR',(0,0),(-1,0),NAVY),('FONTNAME',(0,0),(-1,0),BOLD),('FONTSIZE',(0,0),(-1,0),8.5),
        ('BACKGROUND',(0,1),(-1,-2),PANEL),('BACKGROUND',(0,-1),(-1,-1),PANEL2),('TEXTCOLOR',(0,1),(-1,-1),PALE),('FONTNAME',(0,1),(-1,-1),REG),('FONTNAME',(0,-1),(-1,-1),BOLD),('FONTSIZE',(0,1),(-1,-1),7.8),
        ('GRID',(0,0),(-1,-1),.5,LINE),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),6)
    ]))
    table.wrapOn(c,760,310); table.drawOn(c,42,150)
    card(c,42,55,230,72,"INCREMENTAL PATH","USD 3k - 10k","CT + integration + controlled-water trial",TEAL)
    paragraph(c,"Because the team already owns a BlueROV2 and Omniscan 450 SS, capital already deployed is not counted again in the incremental next gate.",290,115,250,58,9)
    paragraph(c,"Indicative prices checked 21 Jul 2026. Taxes, shipping, certification and local vessel/permit costs are excluded.",565,115,235,58,8.5,color=SAND)


def page_ops(c: Canvas, n: int) -> None:
    bg(c,n,"DEPLOYMENT")
    title(c,"08 / operations","A deployment workflow an operator can adopt","Start supervised and traceable; increase autonomy only after controlled validation.")
    phases=[
        ("BEFORE","Import outfall chart, mixing zone and tide/current context. Run safety checklist and blank-water CT calibration."),
        ("ON SITE","Launch from shore or small vessel. Localize infrastructure by sonar; pilot retains abort authority."),
        ("IN MISSION","Collect baseline then adaptive passes. Watch clearance, uncertainty and budget in the dashboard."),
        ("AFTER","Generate map, 3-D state, evidence ledger and screening verdict. Trigger REVIEW when evidence is insufficient."),
    ]
    for i,(head,text) in enumerate(phases):
        x=42+i*190; c.setFillColor(PANEL); c.roundRect(x,275,174,188,8,stroke=0,fill=1)
        c.setFillColor(TEAL); c.circle(x+25,432,15,stroke=0,fill=1); c.setFillColor(NAVY); c.setFont(BOLD,10); c.drawCentredString(x+25,428,str(i+1))
        c.setFillColor(white); c.setFont(BOLD,12); c.drawString(x+16,389,head)
        paragraph(c,text,x+16,368,142,115,9)
    c.setFillColor(PANEL); c.roundRect(42,58,555,185,8,stroke=0,fill=1)
    paragraph(c,"<b>Why the operating model can be lower-cost</b>",60,221,510,28,14,color=white)
    paragraph(c,"A compact ROV can repeat targeted missions from shore or a small support boat, use a modular sensor package and produce the first map during the same operating cycle. The claim is flexibility and faster screening - not a guaranteed replacement for vessel-based accredited surveys.",60,185,505,93,10)
    c.setFillColor(PANEL); c.roundRect(615,58,187,185,8,stroke=0,fill=1)
    paragraph(c,"<b>Field safeguards</b>",632,221,155,28,13,color=white)
    paragraph(c,"- human abort authority<br/>- geofence and standoff<br/>- tether / snag plan<br/>- sensor blank and reference<br/>- raw-data retention<br/>- REVIEW on uncertainty",632,186,150,112,9,color=CYAN)


def page_roadmap(c: Canvas, n: int) -> None:
    bg(c,n,"ROADMAP AND RISKS")
    title(c,"09 / next gates","From compelling prototype to defensible field evidence","Each phase closes a specific risk before the system claims operational readiness.")
    phases=[
        ("0-3 MONTHS","Payload integration","CT enclosure, time sync, calibration fixture, bench and tank tests.","Gate: stable, traceable sensor stream"),
        ("3-6 MONTHS","Controlled water","Known salinity gradients, sonar target geometry, repeated missions.","Gate: localization + mapping error bounds"),
        ("6-12 MONTHS","Nearshore pilot","Supervised outfall-adjacent trials with permits and reference sampling.","Gate: agreement with independent samples"),
        ("12-18 MONTHS","Operational pilot","Repeat campaigns, dashboard handover, maintenance and unit economics.","Gate: operator acceptance + SOP"),
    ]
    for i,(time,head,body,gate) in enumerate(phases):
        x=42+i*190
        c.setFillColor(PANEL); c.roundRect(x,286,174,196,8,stroke=0,fill=1)
        c.setFillColor(TEAL if i<2 else SAND); c.setFont(BOLD,8); c.drawString(x+15,458,time)
        c.setFillColor(white); c.setFont(BOLD,13); c.drawString(x+15,426,head)
        paragraph(c,body,x+15,402,144,72,9)
        paragraph(c,"<b>"+gate+"</b>",x+15,326,144,44,8.3,color=CYAN)
    c.setFillColor(PANEL); c.roundRect(42,58,760,188,8,stroke=0,fill=1)
    paragraph(c,"<b>Known limitations and how we address them</b>",59,225,720,27,14,color=white)
    risks=[
        ("Simulation-to-water gap","calibrated tank truth + independent grab samples"),
        ("Surrogate plume physics","site current inputs, calibrated transport model, later CFD coupling"),
        ("Long-run sensitivity","multi-pass sonar consensus and stricter abstention policy"),
        ("Navigation / tether hazards","supervised autonomy, geofence, standoff and abort procedure"),
    ]
    for i,(risk,mit) in enumerate(risks):
        x=59+(i%2)*365; y=184-(i//2)*55
        c.setFillColor(CORAL); c.circle(x+5,y+3,3,stroke=0,fill=1)
        paragraph(c,"<b>"+risk+"</b><br/>"+mit,x+16,y+17,325,45,8.6)


def page_close(c: Canvas, n: int) -> None:
    bg(c,n,"COMPETITION SUMMARY")
    fit_image(c,ASSETS/"images/hero_structure.png",0,0,PW,PH,crop=True)
    c.setFillColor(Color(0.015,.08,.11,alpha=.83)); c.rect(0,0,PW,PH,stroke=0,fill=1)
    c.setFillColor(white); c.setFont(BOLD,31); c.drawString(44,PH-66,"A credible prototype with a clear next gate")
    c.setFillColor(CYAN); c.setFont(REG,14); c.drawString(45,PH-91,"Infrastructure localization + adaptive plume mapping + an uncertainty-aware digital twin")
    card(c,44,286,172,105,"CUSTOM ENGINE","1.65 m","sonar localization",TEAL)
    card(c,232,286,172,105,"SAFE MISSION","0","collisions over 220 m",TEAL)
    card(c,420,286,172,105,"3-D TWIN","1,770","simulated samples",CYAN)
    card(c,608,286,172,105,"NEXT GATE","WATER","calibrated CT validation",SAND)
    c.setFillColor(PANEL); c.roundRect(44,110,486,142,8,stroke=0,fill=1)
    paragraph(c,"<b>What support unlocks</b><br/>A calibrated CT integration, controlled-water truth campaign and first supervised nearshore pilot. The team already brings the base ROV, sonar, working software pipeline and a transparent evidence package.",62,229,450,97,11)
    c.setFillColor(PANEL); c.roundRect(550,110,230,142,8,stroke=0,fill=1)
    paragraph(c,"<b>Verified vendor references</b>",566,229,198,25,10,color=white)
    paragraph(c,"BlueROV2: bluerobotics.com/store/rov/bluerov2/<br/>Omniscan 450 FS: bluerobotics.com/store/sonars/imaging-sonars/cerulean-omniscan-450-fs-imaging-sonar/<br/>Prices accessed 21 Jul 2026.",566,202,198,80,7.1,color=MUTED)
    c.setFillColor(SAND); c.setFont(BOLD,9); c.drawString(44,78,"STATUS: INITIAL PROTOTYPE OR MODEL")
    c.setFillColor(PALE); c.setFont(REG,8); c.drawString(44,60,"All performance values are simulation results. BrineWatch is not yet field validated or certified for regulatory compliance.")


def build() -> None:
    OUT.mkdir(parents=True,exist_ok=True)
    c=Canvas(str(PDF),pagesize=PAGE,pageCompression=1)
    c.setTitle("BrineWatch - Competition Report")
    c.setAuthor("BrineWatch team")
    page_cover(c); c.showPage()
    for n,fn in enumerate([page_problem,page_solution,page_engine,page_mapping,page_3d,page_benchmark,page_feasibility,page_ops,page_roadmap,page_close],start=2):
        fn(c,n); c.showPage()
    c.save(); print(PDF)


if __name__=="__main__":
    build()

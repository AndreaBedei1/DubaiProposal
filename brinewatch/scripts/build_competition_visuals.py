"""Build presentation-ready BrineWatch figures from recorded project outputs.

All scene images are genuine HoloOcean RGB captures.  Processing is limited to
crop, resize, colour/contrast correction and layout.  Scientific figures are
rendered directly from the committed mission and volumetric result files.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "brinewatch"
OUT = ROOT / "output" / "submission"
IMAGES = OUT / "images"
FIGURES = OUT / "figures"

NAVY = "#071c27"
INK = "#102a35"
TEAL = "#19c3b1"
CYAN = "#5be7de"
SAND = "#f1c27d"
MUTED = "#7796a1"
PAPER = "#f4f8f7"
CORAL = "#ff7b6b"

CMAP = LinearSegmentedColormap.from_list(
    "brinewatch", ["#082c3a", "#0e6374", "#16a3a5", "#8dd7bd", "#f1c27d", "#ff7b6b"]
)


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/aptos-bold.ttf" if bold else "C:/Windows/Fonts/aptos.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _cover(image: Image.Image, size: tuple[int, int], zoom: float = 1.0, y_bias: float = 0.5) -> Image.Image:
    w, h = image.size
    tw, th = size
    scale = max(tw / w, th / h) * zoom
    resized = image.resize((round(w * scale), round(h * scale)), Image.Resampling.LANCZOS)
    left = max(0, (resized.width - tw) // 2)
    available_y = max(0, resized.height - th)
    top = round(available_y * y_bias)
    return resized.crop((left, top, left + tw, top + th))


def _grade(image: Image.Image) -> Image.Image:
    """Moderate underwater grade without adding or removing scene content."""
    img = image.convert("RGB")
    img = ImageEnhance.Contrast(img).enhance(1.10)
    img = ImageEnhance.Color(img).enhance(1.08)
    img = ImageEnhance.Brightness(img).enhance(0.96)
    img = ImageEnhance.Sharpness(img).enhance(1.18)
    arr = np.asarray(img).astype(np.float32)
    # A restrained blue-green atmospheric grade.  The source already contains
    # physical HoloOcean water haze; this only balances the presentation.
    arr[..., 0] *= 0.94
    arr[..., 1] *= 1.02
    arr[..., 2] *= 1.04
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def build_scene_assets() -> None:
    source = PROJECT / "outputs" / "visual" / "selected_world"
    IMAGES.mkdir(parents=True, exist_ok=True)

    selections = {
        "hero_structure.png": ("04_three_quarter_risers.png", 1.08, 0.52),
        "hero_structure_wide.png": ("02_elevated_oblique.png", 1.00, 0.50),
        "inspection_closeup.png": ("05_close_nozzles.png", 1.04, 0.55),
        "mission_approach.png": ("09_mission_approach.png", 1.00, 0.50),
    }
    for target, (name, zoom, y_bias) in selections.items():
        img = _grade(_cover(Image.open(source / name), (1920, 1080), zoom=zoom, y_bias=y_bias))
        img.save(IMAGES / target, quality=95)

    hero = Image.open(IMAGES / "hero_structure.png").convert("RGB")
    overlay = Image.new("RGBA", hero.size, (0, 0, 0, 0))
    px = overlay.load()
    for y in range(hero.height):
        alpha = int(175 * max(0, 1 - y / 430)) + int(120 * max(0, (y - 850) / 230))
        for x in range(hero.width):
            px[x, y] = (4, 24, 35, min(190, alpha))
    titled = Image.alpha_composite(hero.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(titled)
    draw.text((92, 72), "BRINEWATCH", fill="white", font=_font(76, bold=True))
    draw.text((96, 164), "Autonomous intelligence for desalination outfalls", fill=(185, 244, 234), font=_font(34))
    draw.rounded_rectangle((94, 914, 897, 1003), radius=20, fill=(5, 30, 42, 210), outline=(91, 231, 222, 170), width=2)
    draw.text((126, 938), "Genuine HoloOcean scene  |  simulation prototype", fill="white", font=_font(27))
    titled.convert("RGB").save(IMAGES / "hero_structure_annotated.png", quality=95)

    names = [
        ("02_elevated_oblique.png", "SITE OVERVIEW"),
        ("04_three_quarter_risers.png", "DIFFUSER APPROACH"),
        ("05_close_nozzles.png", "RISER INSPECTION"),
        ("07_rov_scale_riser.png", "STRUCTURE DETAIL"),
        ("09_mission_approach.png", "MISSION CONTEXT"),
        ("10_departure.png", "SURVEY EXIT"),
    ]
    sheet = Image.new("RGB", (2400, 1530), (7, 28, 39))
    draw = ImageDraw.Draw(sheet)
    draw.text((80, 44), "BRINEWATCH  /  UNDERWATER STRUCTURE STUDY", fill="white", font=_font(50, bold=True))
    draw.text((82, 110), "Genuine HoloOcean RGB captures - selected and colour balanced for presentation", fill=(166, 211, 213), font=_font(25))
    for i, (name, label) in enumerate(names):
        row, col = divmod(i, 3)
        x, y = 80 + col * 775, 178 + row * 640
        cell = _grade(_cover(Image.open(source / name), (720, 500), zoom=1.02))
        sheet.paste(cell, (x, y))
        draw.rectangle((x, y + 500, x + 720, y + 565), fill=(10, 48, 61))
        draw.text((x + 22, y + 516), label, fill=(204, 247, 239), font=_font(25, bold=True))
    sheet.save(IMAGES / "structure_contact_sheet.png", quality=94)


def _style_ax(ax: plt.Axes, title: str) -> None:
    ax.set_facecolor("#0b2a36")
    ax.set_title(title, color="white", fontsize=15, fontweight="bold", loc="left", pad=14)
    ax.tick_params(colors="#b8d4d7", labelsize=9)
    for spine in ax.spines.values():
        spine.set_color("#315663")
    ax.grid(color="white", alpha=0.10, linewidth=0.7)


def build_localization_figure() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    data = json.loads((PROJECT / "outputs/custom_holoocean_mission/run1/locate_result.json").read_text())
    sonar = Image.open(PROJECT / "docs/application/pfh2026/assets/sonar/gate/sonar_present_r12.png")

    fig = plt.figure(figsize=(16, 7.8), facecolor=NAVY)
    gs = fig.add_gridspec(1, 3, width_ratios=[1.08, 1.15, 0.77], left=.05, right=.97, top=.84, bottom=.12, wspace=.20)
    ax0 = fig.add_subplot(gs[0, 0])
    _style_ax(ax0, "01  Multi-aspect sonar localization")
    prior = np.asarray(data["prior"])
    estimate = np.asarray(data["estimate"])
    truth = np.array([40.0, 0.0])
    theta = np.linspace(0, 2*np.pi, data["ring_poses"], endpoint=False)
    ring = prior[:, None] + data["ring_radius_m"] * np.vstack([np.cos(theta), np.sin(theta)])
    ax0.plot(np.r_[ring[0], ring[0,0]], np.r_[ring[1], ring[1,0]], color=CYAN, alpha=.55, linewidth=1.4)
    ax0.scatter(ring[0], ring[1], s=50, c=np.linspace(0, 1, len(theta)), cmap="winter", edgecolor="white", linewidth=.45, label="16 sonar poses")
    ax0.scatter(*prior, marker="+", s=220, color=SAND, linewidth=3, label="chart prior")
    ax0.scatter(*estimate, marker="X", s=160, color=CORAL, edgecolor="white", linewidth=1, label="sonar estimate")
    ax0.scatter(*truth, marker="*", s=210, color="white", edgecolor=INK, linewidth=.8, label="diffuser centre")
    ax0.plot([estimate[0], truth[0]], [estimate[1], truth[1]], "--", color=CORAL, linewidth=2)
    ax0.annotate("1.65 m", xy=(estimate+truth)/2, xytext=(9, -22), textcoords="offset points", color="white", fontsize=12, fontweight="bold")
    ax0.set_aspect("equal")
    ax0.set_xlabel("east (m)", color="#b8d4d7")
    ax0.set_ylabel("north (m)", color="#b8d4d7")
    leg=ax0.legend(loc="lower left", frameon=False, fontsize=9)
    for t in leg.get_texts(): t.set_color("white")

    ax1 = fig.add_subplot(gs[0, 1])
    _style_ax(ax1, "02  Native simulated imaging sonar")
    ax1.imshow(sonar, cmap="magma", aspect="auto")
    ax1.set_xticks([]); ax1.set_yticks([])
    ax1.text(.03, .05, "Recorded structure-present frame", transform=ax1.transAxes, color="white", fontsize=11,
             bbox=dict(boxstyle="round,pad=.5", facecolor="#071c27", alpha=.80, edgecolor="#4ad9ce"))

    ax2 = fig.add_subplot(gs[0, 2])
    ax2.set_facecolor("#0b2a36"); ax2.axis("off")
    ax2.text(0, .96, "EVIDENCE", color=CYAN, fontsize=13, fontweight="bold", va="top")
    metrics = [
        ("47", "residual sonar contacts"),
        ("22", "consensus inliers"),
        ("270 deg", "aspect coverage"),
        ("1.65 m", "centre error"),
    ]
    y=.82
    for value,label in metrics:
        ax2.text(0, y, value, color="white", fontsize=27, fontweight="bold", va="top")
        ax2.text(0, y-.075, label, color="#a7c7cc", fontsize=11, va="top")
        ax2.plot([0,.92],[y-.12,y-.12], color="#315663", lw=.8)
        y-=.19
    ax2.text(0, .015, "0 ground-truth inputs to localizer\nCustom-engine mission; no oracle fallback", color=SAND, fontsize=10.5, va="bottom", linespacing=1.4)

    fig.suptitle("SEE THE OUTFALL BEFORE MAPPING THE PLUME", color="white", fontsize=25, fontweight="bold", x=.05, ha="left", y=.965)
    fig.text(.05, .905, "A chart prior narrows the search; a full sonar ring converts multi-view residuals into a robust location estimate.", color="#a7c7cc", fontsize=12)
    fig.savefig(FIGURES / "sonar_localization.png", dpi=180, facecolor=fig.get_facecolor())
    plt.close(fig)


def build_mission_figure() -> None:
    d=np.load(PROJECT / "outputs/custom_holoocean_mission/run1/plume_maps.npz")
    samples=np.genfromtxt(PROJECT / "outputs/custom_holoocean_mission/run1/samples.csv", delimiter=",", names=True)
    summary=json.loads((PROJECT / "outputs/custom_holoocean_mission/run1/summary.json").read_text())
    fig, axes=plt.subplots(1,3,figsize=(16,6.8),facecolor=NAVY,constrained_layout=True)
    x0,x1=float(d['X'].min()),float(d['X'].max()); y0,y1=float(d['Y'].min()),float(d['Y'].max())
    for ax in axes: _style_ax(ax, "")
    im0=axes[0].imshow(d['mean'],origin='lower',extent=[x0,x1,y0,y1],cmap=CMAP,vmin=39.5,vmax=47.8,aspect='equal')
    axes[0].plot(samples['x'],samples['y'],color='white',lw=1.6,alpha=.72)
    axes[0].scatter(samples['x'][::10],samples['y'][::10],s=8,color=CYAN,alpha=.85)
    axes[0].scatter(*summary['outfall_estimate'],marker='*',s=180,color=SAND,edgecolor=NAVY,zorder=5)
    axes[0].set_title("01  Adaptive sampling trajectory",loc='left',color='white',fontweight='bold')
    axes[0].set_xlabel('east (m)',color='#b8d4d7'); axes[0].set_ylabel('north (m)',color='#b8d4d7')
    axes[0].text(.03,.03,"271 CT samples  |  220 m route",transform=axes[0].transAxes,color='white',fontsize=10,bbox=dict(boxstyle='round,pad=.45',facecolor=NAVY,alpha=.82,edgecolor=TEAL))
    im1=axes[1].imshow(d['mean'],origin='lower',extent=[x0,x1,y0,y1],cmap=CMAP,vmin=39.5,vmax=47.8,aspect='equal')
    cs=axes[1].contour(d['X'],d['Y'],d['mean'],levels=[41.651],colors=['white'],linewidths=2.4)
    axes[1].clabel(cs,fmt={41.651:'screening boundary'},inline=True,fontsize=8)
    axes[1].set_title("02  Reconstructed salinity",loc='left',color='white',fontweight='bold')
    axes[1].set_xlabel('east (m)',color='#b8d4d7'); axes[1].set_ylabel('north (m)',color='#b8d4d7')
    cb=fig.colorbar(im1,ax=axes[1],fraction=.045,pad=.03); cb.set_label('salinity (PSU)',color='white'); cb.ax.tick_params(colors='white')
    im2=axes[2].imshow(d['std'],origin='lower',extent=[x0,x1,y0,y1],cmap='magma',aspect='equal')
    axes[2].set_title("03  Model uncertainty",loc='left',color='white',fontweight='bold')
    axes[2].set_xlabel('east (m)',color='#b8d4d7'); axes[2].set_ylabel('north (m)',color='#b8d4d7')
    cb=fig.colorbar(im2,ax=axes[2],fraction=.045,pad=.03); cb.set_label('posterior std (PSU)',color='white'); cb.ax.tick_params(colors='white')
    fig.suptitle("FROM PATH TO ACTIONABLE PLUME MAP",x=.01,ha='left',color='white',fontsize=24,fontweight='bold')
    fig.savefig(FIGURES / "mission_reconstruction.png",dpi=180,facecolor=fig.get_facecolor())
    plt.close(fig)


def build_volumetric_figure() -> None:
    d=np.load(PROJECT / "outputs/volumetric/adaptive_run1/volume.npz")
    summary=json.loads((PROJECT / "outputs/volumetric/adaptive_run1/volumetric_summary.json").read_text())
    mean=d['mean']; threshold=float(d['threshold']); mask=mean>=threshold
    x,y,z=d['X'][mask],d['Y'][mask],d['Z'][mask]; val=mean[mask]
    fig=plt.figure(figsize=(15,8.5),facecolor=NAVY)
    ax=fig.add_axes([.04,.12,.68,.76],projection='3d',facecolor=NAVY)
    order=np.argsort(val)
    sc=ax.scatter(x[order],y[order],z[order],c=val[order],cmap=CMAP,s=22,alpha=.62,linewidths=0,depthshade=True)
    # Draw three measured altitude layers, presented as sampling concept not a fake route.
    bed=float(d['Z'].min())
    for alt,color in zip(summary['altitudes_m'],["#57d8cf","#8ce3c5","#f1c27d"]):
        zz=bed+alt
        ax.plot([-59,59,59,-59,-59],[-59,-59,59,59,-59],[zz]*5,color=color,lw=.8,alpha=.25)
    xx=np.linspace(-59,59,2); yy=np.linspace(-59,59,2); XX,YY=np.meshgrid(xx,yy)
    ax.plot_surface(XX,YY,np.full_like(XX,bed),color='#a99d83',alpha=.24,shade=False)
    ax.scatter([-40],[0],[bed+1.0],marker='*',s=180,color='white',edgecolor=INK,label='outfall')
    ax.set_xlabel('east (m)',color='#b8d4d7',labelpad=8); ax.set_ylabel('north (m)',color='#b8d4d7',labelpad=8); ax.set_zlabel('depth (m)',color='#b8d4d7',labelpad=8)
    ax.tick_params(colors='#b8d4d7',labelsize=9); ax.view_init(elev=25,azim=-55)
    ax.xaxis.pane.set_facecolor((.03,.12,.16,.3)); ax.yaxis.pane.set_facecolor((.03,.12,.16,.3)); ax.zaxis.pane.set_facecolor((.03,.12,.16,.3))
    cb=fig.colorbar(sc,ax=ax,fraction=.03,pad=.02,shrink=.7); cb.set_label('estimated salinity (PSU)',color='white'); cb.ax.tick_params(colors='white')
    panel=fig.add_axes([.75,.18,.22,.62]); panel.axis('off')
    panel.text(0,1,"VOLUMETRIC TWIN",color=CYAN,fontsize=13,fontweight='bold',va='top')
    rows=[
        ("1,770","samples across 3 altitudes"),
        ("5,477 m3","estimated volume above threshold"),
        ("2.31 PSU","3-D reconstruction RMSE"),
        ("0.399","volume intersection-over-union"),
        ("8.0 m","mapped plume-top height"),
    ]
    ypos=.86
    for v,l in rows:
        panel.text(0,ypos,v,color='white',fontsize=22,fontweight='bold',va='top'); panel.text(0,ypos-.07,l,color='#a7c7cc',fontsize=10,va='top'); ypos-=.16
    panel.text(0,.01,"Simulation-based plume surrogate\n(not CFD or field ground truth)",color=SAND,fontsize=10,va='bottom',linespacing=1.4)
    fig.suptitle("A 3-D VIEW OF WHERE THE PLUME GOES",x=.05,ha='left',y=.97,color='white',fontsize=25,fontweight='bold')
    fig.text(.05,.91,"Multi-altitude sampling updates a volumetric salinity estimate and exposes uncertainty for the next mission.",color='#a7c7cc',fontsize=12)
    fig.savefig(FIGURES / "plume_3d.png",dpi=180,facecolor=fig.get_facecolor())
    plt.close(fig)


def build_digital_twin_figure() -> None:
    d=np.load(PROJECT / "outputs/custom_holoocean_mission/run1/plume_maps.npz")
    summary=json.loads((PROJECT / "outputs/custom_holoocean_mission/run1/summary.json").read_text())
    fig=plt.figure(figsize=(16,9),facecolor=NAVY)
    fig.text(.045,.94,"BRINEWATCH DIGITAL TWIN",color='white',fontsize=27,fontweight='bold')
    fig.text(.045,.895,"Mission evidence in one operational view",color='#9cc4c8',fontsize=13)
    # KPI cards
    cards=[("OUTFALL FOUND","1.65 m","sonar centre error",TEAL),("SAFE SURVEY","0","collisions",TEAL),("SCREENING","REVIEW","uncertainty retained",SAND),("MAP QUALITY","0.686","boundary F1",CYAN)]
    for i,(head,val,sub,col) in enumerate(cards):
        ax=fig.add_axes([.045+i*.235,.695,.215,.155]); ax.set_facecolor('#0c303d'); ax.set_xticks([]); ax.set_yticks([])
        for s in ax.spines.values(): s.set_color('#315663')
        ax.text(.06,.80,head,color='#95b8bd',fontsize=10,fontweight='bold',va='top'); ax.text(.06,.52,val,color=col,fontsize=27,fontweight='bold',va='top'); ax.text(.06,.12,sub,color='white',fontsize=10,va='bottom')
    # map
    ax=fig.add_axes([.045,.12,.51,.51]); _style_ax(ax,"LIVE SITE STATE  /  estimated salinity")
    x0,x1=float(d['X'].min()),float(d['X'].max()); y0,y1=float(d['Y'].min()),float(d['Y'].max())
    im=ax.imshow(d['mean'],origin='lower',extent=[x0,x1,y0,y1],cmap=CMAP,vmin=39.5,vmax=47.8,aspect='auto')
    ax.contour(d['X'],d['Y'],d['mean'],levels=[41.651],colors=['white'],linewidths=2)
    traj=d['trajectory']; ax.plot(traj[:,1],traj[:,2],color=CYAN,lw=1.2,alpha=.75)
    ax.scatter(*summary['outfall_estimate'],marker='*',s=150,color=SAND,edgecolor=NAVY)
    ax.set_xlabel('east (m)',color='#b8d4d7'); ax.set_ylabel('north (m)',color='#b8d4d7')
    cb=fig.colorbar(im,ax=ax,fraction=.035,pad=.025); cb.ax.tick_params(colors='white'); cb.set_label('PSU',color='white')
    # flow and decisions
    flow=fig.add_axes([.60,.12,.355,.51]); flow.set_facecolor('#0b2a36'); flow.set_xlim(0,1); flow.set_ylim(0,1); flow.axis('off')
    flow.text(0,1,"HOW THE TWIN UPDATES",color='white',fontsize=15,fontweight='bold',va='top')
    steps=[("1","SONAR", "locate infrastructure"),("2","CT SAMPLING","measure salinity + temperature"),("3","GP UPDATE","reconstruct field + uncertainty"),("4","ADAPT","prioritize boundaries and gaps"),("5","SCREEN","CLEAR / REVIEW / POSSIBLE EXCEEDANCE")]
    y=.82
    for n,title,desc in steps:
        flow.text(.02,y,n,color=NAVY,fontsize=12,fontweight='bold',ha='center',va='center',bbox=dict(boxstyle='circle,pad=.45',facecolor=TEAL,edgecolor='none'))
        flow.text(.11,y+.025,title,color='white',fontsize=12,fontweight='bold',va='center'); flow.text(.11,y-.035,desc,color='#9fc1c6',fontsize=10,va='center')
        if n!='5': flow.plot([.02,.02],[y-.075,y-.135],color='#3b6973',lw=2)
        y-=.16
    flow.text(0,.01,"Prototype scope: simulator + analytic plume surrogate.\nNext gate: calibrated CT payload and controlled-water validation.",color=SAND,fontsize=10,va='bottom',linespacing=1.45)
    fig.savefig(FIGURES / "digital_twin_dashboard.png",dpi=180,facecolor=fig.get_facecolor())
    plt.close(fig)


def build_benchmark_figure() -> None:
    p=PROJECT / "outputs/brinewatch_benchmark_dynamic_20260721_211914/benchmark_summary.json"
    d=json.loads(p.read_text())
    budgets=np.array([25,50,75,100]); keys=['0.25','0.5','0.75','1']
    l=np.array([d['lawnmower'][k]['rmse_plume']['mean'] for k in keys]); a=np.array([d['adaptive'][k]['rmse_plume']['mean'] for k in keys])
    lf=np.array([d['lawnmower'][k]['boundary_f1']['mean'] for k in keys]); af=np.array([d['adaptive'][k]['boundary_f1']['mean'] for k in keys])
    fig,axs=plt.subplots(1,2,figsize=(13.5,5.8),facecolor=NAVY)
    fig.subplots_adjust(left=.06,right=.98,top=.83,bottom=.18,wspace=.12)
    for ax in axs: _style_ax(ax,"")
    axs[0].plot(budgets,l,'o-',color='#95a8ad',lw=2.2,label='lawnmower'); axs[0].plot(budgets,a,'o-',color=TEAL,lw=2.8,label='adaptive')
    axs[0].set_title('Plume RMSE  |  lower is better',loc='left',color='white',fontweight='bold'); axs[0].set_ylabel('RMSE (PSU)',color='#b8d4d7'); axs[0].set_xlabel('travel budget used (%)',color='#b8d4d7')
    axs[0].annotate('18.7% lower',xy=(50,a[1]),xytext=(57,1.22),color='white',arrowprops=dict(arrowstyle='->',color=TEAL),fontsize=11,fontweight='bold')
    axs[1].plot(budgets,lf,'o-',color='#95a8ad',lw=2.2,label='lawnmower'); axs[1].plot(budgets,af,'o-',color=TEAL,lw=2.8,label='adaptive')
    axs[1].set_title('Boundary F1  |  higher is better',loc='left',color='white',fontweight='bold'); axs[1].set_ylabel('F1 score',color='#b8d4d7'); axs[1].set_xlabel('travel budget used (%)',color='#b8d4d7')
    axs[1].annotate('+14.2%',xy=(50,af[1]),xytext=(58,.62),color='white',arrowprops=dict(arrowstyle='->',color=TEAL),fontsize=11,fontweight='bold')
    for ax in axs:
        leg=ax.legend(frameon=False,loc='best'); [t.set_color('white') for t in leg.get_texts()]
    fig.suptitle('ADAPTIVE SAMPLING HELPS MOST WHEN TIME IS LIMITED',x=.02,ha='left',color='white',fontsize=22,fontweight='bold')
    fig.text(.06,.055,'Dynamic-plume simulation benchmark: 12 held-out seeds, equal travel budgets. At full coverage, the regular lawnmower path is stronger - a useful design boundary, not a hidden result.',color='#a7c7cc',fontsize=9.5)
    fig.savefig(FIGURES/'benchmark_efficiency.png',dpi=180,facecolor=fig.get_facecolor())
    plt.close(fig)


def main() -> None:
    build_scene_assets()
    build_localization_figure()
    build_mission_figure()
    build_volumetric_figure()
    build_digital_twin_figure()
    build_benchmark_figure()
    print(f"Competition visuals written to {OUT}")


if __name__ == "__main__":
    main()

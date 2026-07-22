"""Create smooth competition videos from genuine simulator/result frames.

The cinematic sequence is intentionally separated from the scientific mission:
it uses slow virtual camera moves over recorded HoloOcean RGB captures, then
shows figures generated from recorded mission data.  It is not presented as a
continuous telemetry-synchronised replay.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "output" / "submission"
VIDEO_DIR = PACKAGE / "video"
IMAGES = PACKAGE / "images"
FIGURES = PACKAGE / "figures"

W, H = 1280, 720
FPS = 24


def font(size: int, bold: bool = False):
    for path in [
        Path("C:/Windows/Fonts/aptos-bold.ttf" if bold else "C:/Windows/Fonts/aptos.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
    ]:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


@dataclass
class Shot:
    path: Path
    duration: float
    kicker: str
    title: str
    subtitle: str
    zoom0: float = 1.0
    zoom1: float = 1.06
    pan0: tuple[float, float] = (0.5, 0.5)
    pan1: tuple[float, float] = (0.5, 0.5)
    darken: float = 0.10


def cover_array(path: Path) -> np.ndarray:
    im = Image.open(path).convert("RGB")
    scale = max(W / im.width, H / im.height)
    im = im.resize((round(im.width * scale), round(im.height * scale)), Image.Resampling.LANCZOS)
    left = (im.width - W) // 2
    top = (im.height - H) // 2
    return np.asarray(im.crop((left, top, left + W, top + H)))


def ease(t: float) -> float:
    return t * t * (3.0 - 2.0 * t)


def move(base: np.ndarray, t: float, shot: Shot) -> np.ndarray:
    t = ease(t)
    zoom = shot.zoom0 + (shot.zoom1 - shot.zoom0) * t
    cx = (shot.pan0[0] + (shot.pan1[0] - shot.pan0[0]) * t) * W
    cy = (shot.pan0[1] + (shot.pan1[1] - shot.pan0[1]) * t) * H
    cw, ch = W / zoom, H / zoom
    x0 = int(np.clip(cx - cw / 2, 0, W - cw))
    y0 = int(np.clip(cy - ch / 2, 0, H - ch))
    crop = base[y0 : y0 + int(ch), x0 : x0 + int(cw)]
    return cv2.resize(crop, (W, H), interpolation=cv2.INTER_CUBIC)


def caption(frame: np.ndarray, shot: Shot, progress: float) -> np.ndarray:
    img = Image.fromarray(frame).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    alpha = int(210 * min(1.0, progress / .12, (1.0 - progress) / .10))
    alpha = max(0, alpha)
    draw.rectangle((0, 0, W, H), fill=(3, 20, 29, int(255 * shot.darken)))
    draw.rounded_rectangle((54, 500, 1040, 663), radius=16, fill=(4, 26, 37, int(alpha * .92)), outline=(56, 204, 193, alpha), width=2)
    draw.text((82, 523), shot.kicker, font=font(18, True), fill=(91, 231, 222, alpha))
    draw.text((82, 552), shot.title, font=font(38, True), fill=(255, 255, 255, alpha))
    draw.text((84, 607), shot.subtitle, font=font(21), fill=(190, 220, 221, alpha))
    draw.text((1130, 32), "BRINEWATCH", font=font(15, True), fill=(255, 255, 255, 155))
    return np.asarray(Image.alpha_composite(img, overlay).convert("RGB"))


def render_shot(shot: Shot) -> list[np.ndarray]:
    base = cover_array(shot.path)
    count = max(2, round(shot.duration * FPS))
    return [caption(move(base, i / (count - 1), shot), shot, i / (count - 1)) for i in range(count)]


def write_sequence(path: Path, shots: list[Shot], fade_seconds: float = .55) -> float:
    """Render one shot at a time so a 1080p-sized frame list is never retained."""
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    if not writer.isOpened():
        raise RuntimeError("OpenCV could not open the MP4 writer")
    overlap = round(fade_seconds * FPS)
    pending = render_shot(shots[0])
    written = 0
    for shot in shots[1:]:
        nxt = render_shot(shot)
        n = min(overlap, len(pending), len(nxt))
        for frame in pending[:-n]:
            writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)); written += 1
        for i in range(n):
            a = ease((i + 1) / (n + 1))
            frame = cv2.addWeighted(pending[-n+i], 1-a, nxt[i], a, 0)
            writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)); written += 1
        pending = nxt[n:]
    for frame in pending:
        writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)); written += 1
    writer.release()
    return written / FPS


def contact_sheet(video: Path, output: Path, count: int = 10) -> None:
    cap = cv2.VideoCapture(str(video))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    selected=[]
    for idx in np.linspace(0, max(0,total-1), count, dtype=int):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx)); ok, frame=cap.read()
        if ok:
            selected.append(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB))
    cap.release()
    thumb_w,thumb_h=480,270
    sheet=Image.new('RGB',(thumb_w*2,thumb_h*5+90),(7,28,39)); draw=ImageDraw.Draw(sheet)
    draw.text((26,22),'BRINEWATCH FINAL VIDEO  /  SELECTED FRAMES',font=font(28,True),fill='white')
    for i,arr in enumerate(selected):
        im=Image.fromarray(arr).resize((thumb_w,thumb_h),Image.Resampling.LANCZOS)
        x=(i%2)*thumb_w; y=90+(i//2)*thumb_h; sheet.paste(im,(x,y))
    sheet.save(output,quality=92)


def final_shot() -> Image.Image:
    base=Image.open(IMAGES/'hero_structure.png').convert('RGBA')
    overlay=Image.new('RGBA',base.size,(4,22,31,175)); img=Image.alpha_composite(base,overlay)
    draw=ImageDraw.Draw(img)
    draw.text((90,78),'BRINEWATCH',font=font(72,True),fill='white')
    draw.text((94,169),'Faster evidence. Better sampling. Safer decisions.',font=font(34),fill=(169,241,231))
    metrics=[('1.65 m','sonar localization'),('0','mission collisions'),('1,770','3-D samples')]
    for i,(v,label) in enumerate(metrics):
        x=95+i*520
        draw.text((x,505),v,font=font(53,True),fill=(91,231,222))
        draw.text((x,570),label,font=font(24),fill='white')
    draw.text((94,875),'INITIAL PROTOTYPE OR MODEL  |  simulation evidence today, controlled-water validation next',font=font(25),fill=(241,194,125))
    out=VIDEO_DIR/'final_card.png'; out.parent.mkdir(parents=True,exist_ok=True); img.convert('RGB').save(out,quality=94)
    return img


def build() -> None:
    final_shot()
    long_shots=[
        Shot(IMAGES/'hero_structure_annotated.png',4.8,'THE CHALLENGE','Brine leaves the plant underwater','Operators need faster, spatial evidence near the diffuser.',1.0,1.05,(.50,.52),(.55,.57),.03),
        Shot(IMAGES/'hero_structure_wide.png',5.2,'ROV CAMERA  /  DESCENT','Enter the submerged outfall site','Moderate blue-green haze keeps the structure readable and the scene credible.',1.0,1.10,(.48,.42),(.53,.57),.05),
        Shot(IMAGES/'mission_approach.png',4.4,'ROV CAMERA  /  APPROACH','Acquire the diffuser early','A deliberate, smooth approach replaces oscillatory onboard footage.',1.0,1.13,(.52,.48),(.54,.58),.04),
        Shot(IMAGES/'hero_structure.png',5.0,'ROV CAMERA  /  INSPECT','Hold visual context while sensing','The accepted outfall geometry remains unchanged.',1.02,1.12,(.48,.53),(.58,.57),.03),
        Shot(IMAGES/'inspection_closeup.png',3.7,'STRUCTURE INSPECTION','Check the risers and nozzles','Sonar provides localization where optical visibility may degrade.',1.0,1.08,(.45,.47),(.58,.54),.02),
        Shot(FIGURES/'sonar_localization.png',6.2,'SONAR LOCALIZATION','Find first, then map','16 aspects, 47 residual contacts and a 1.65 m centre error.',1.0,1.035,(.50,.50),(.47,.50),.00),
        Shot(FIGURES/'mission_reconstruction.png',6.2,'ADAPTIVE MISSION','Spend distance where information matters','271 CT samples along a 220 m collision-free in-engine survey.',1.0,1.025,(.50,.50),(.50,.50),.00),
        Shot(FIGURES/'plume_3d.png',6.2,'VOLUMETRIC DIGITAL TWIN','Map the plume in three dimensions','1,770 simulated samples across three altitudes; uncertainty remains visible.',1.0,1.025,(.50,.50),(.50,.50),.00),
        Shot(FIGURES/'digital_twin_dashboard.png',6.0,'MISSION TO DECISION','Update a shared operational picture','Sonar, CT data, reconstruction and screening in one traceable loop.',1.0,1.025,(.50,.50),(.50,.50),.00),
        Shot(VIDEO_DIR/'final_card.png',5.2,'PROTOTYPE STATUS','Ready for the next validation gate','Owned ROV + sonar; calibrated CT integration and controlled-water trials next.',1.0,1.02,(.50,.50),(.50,.50),.00),
    ]
    final=VIDEO_DIR/'BrineWatch_PFH2026_Final.mp4'; long_duration=write_sequence(final,long_shots)
    contact_sheet(final,VIDEO_DIR/'BrineWatch_PFH2026_Final_contact_sheet.jpg')

    short_shots=[long_shots[i] for i in [0,1,2,3,5,6,7,8,9]]
    for s,d in zip(short_shots,[3.2,3.2,2.8,3.1,3.7,3.7,3.7,3.5,3.3]): s.duration=d
    short=VIDEO_DIR/'BrineWatch_PFH2026_Short.mp4'; short_duration=write_sequence(short,short_shots,fade_seconds=.4)
    print(f"Wrote {final} ({long_duration:.1f} s)")
    print(f"Wrote {short} ({short_duration:.1f} s)")


if __name__=='__main__':
    build()

"""Assemble the simplified public BrineWatch Full-HD competition video."""
from __future__ import annotations

import argparse
from functools import lru_cache
import json
from pathlib import Path
import shutil
import subprocess

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
W, H, FPS = 1920, 1080, 30
BG = (29, 23, 6)          # BGR #06171d
PANEL = (51, 42, 12)      # BGR #0c2a33
TEAL = (191, 212, 45)     # BGR #2dd4bf
CYAN = (248, 189, 56)     # BGR #38bdf8
WHITE = (252, 251, 244)
MUTED = (198, 192, 167)
WARM = (36, 191, 251)     # BGR #fbbf24
CORAL = (133, 113, 251)   # BGR #fb7185
FONT_REGULAR = Path(r"C:\Windows\Fonts\segoeui.ttf")
FONT_SEMIBOLD = Path(r"C:\Windows\Fonts\seguisb.ttf")


def ffmpeg_executable():
    """Return a local FFmpeg binary with libx264 support."""
    discovered = shutil.which("ffmpeg")
    if discovered:
        return discovered
    try:
        import imageio_ffmpeg
    except ImportError as exc:
        raise RuntimeError(
            "High-quality video export requires FFmpeg. Install the bundled "
            "binary with: python -m pip install imageio-ffmpeg"
        ) from exc
    return imageio_ffmpeg.get_ffmpeg_exe()


class H264Writer:
    """Stream BGR frames to a visually transparent H.264/MP4 export."""

    def __init__(self, path, crf=15, preset="medium"):
        self.path = Path(path)
        command = [
            ffmpeg_executable(), "-y", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "bgr24",
            "-s:v", f"{W}x{H}", "-r", str(FPS), "-i", "-",
            "-an", "-c:v", "libx264", "-preset", preset,
            "-crf", str(crf), "-profile:v", "high",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(self.path),
        ]
        self.process = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

    def write(self, frame):
        if frame.shape != (H, W, 3) or frame.dtype != np.uint8:
            raise ValueError(f"unexpected output frame {frame.shape} / {frame.dtype}")
        try:
            self.process.stdin.write(np.ascontiguousarray(frame).tobytes())
        except BrokenPipeError as exc:
            error = self.process.stderr.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"FFmpeg stopped while encoding: {error}") from exc

    def release(self):
        self.process.stdin.close()
        error = self.process.stderr.read().decode("utf-8", errors="replace")
        return_code = self.process.wait()
        if return_code:
            raise RuntimeError(f"FFmpeg export failed ({return_code}): {error}")


@lru_cache(maxsize=32)
def video_font(size_px, semibold):
    path = FONT_SEMIBOLD if semibold else FONT_REGULAR
    if not path.exists():
        raise FileNotFoundError(f"Required presentation font not found: {path}")
    return ImageFont.truetype(str(path), size_px)


def text_block(frame, entries):
    """Draw a group of anti-aliased Segoe UI labels with one frame conversion."""
    image = Image.fromarray(frame)
    draw = ImageDraw.Draw(image)
    for value, xy, size, color, thickness in entries:
        size_px = max(12, int(round(size * 46)))
        draw.text(
            xy, value, font=video_font(size_px, thickness >= 2),
            fill=tuple(int(channel) for channel in color), anchor="ls",
        )
    frame[:] = np.asarray(image)


def text(frame, value, xy, size, color=WHITE, thickness=2):
    text_block(frame, [(value, xy, size, color, thickness)])


def fit_size(value, size, bold, max_width):
    """Shrink a label's scale until it fits max_width pixels (never below 60%)."""
    for _ in range(24):
        size_px = max(12, int(round(size * 46)))
        if video_font(size_px, bold).getlength(value) <= max_width:
            break
        if size <= 0.36:
            break
        size -= 0.02
    return size


_FOG_CACHE = {}


def grade_underwater(frame):
    """Underwater look for genuine engine footage only (never scientific figures):
    compress the strong surface-light highlights, cool the colour cast, add a
    depth-fog gradient (denser towards the surface) and a gentle vignette.
    Purely stylistic: geometry and content are unchanged."""
    x = frame.astype(np.float32) / 255.0
    # 1. tame the sun glare: soft roll-off of the top of the tonal range
    x = np.where(x > 0.55, 0.55 + (x - 0.55) * 0.50, x)
    # 2. cool water cast (BGR gains)
    x[..., 2] *= 0.78
    x[..., 1] *= 0.99
    x[..., 0] *= 1.06
    # 3. restrained unsharp before fogging (counteracts TAA softness)
    x = np.clip(x, 0, 1)
    soft = cv2.GaussianBlur(x, (0, 0), .85)
    x = np.clip(x * 1.10 - soft * 0.10, 0, 1)
    # 4. blue depth fog, denser towards the surface (top of frame)
    h, w = x.shape[:2]
    key = (h, w)
    if key not in _FOG_CACHE:
        yy = np.linspace(1, 0, h, dtype=np.float32)[:, None]
        _FOG_CACHE[key] = (0.10 + 0.50 * yy ** 1.5)[..., None]
    fog_alpha = _FOG_CACHE[key]
    fog = np.array([0.55, 0.42, 0.23], dtype=np.float32)  # BGR
    x = x * (1 - fog_alpha) + fog * fog_alpha
    # 5. gentle contrast and saturation
    x = np.clip((x - 0.5) * 1.06 + 0.5, 0, 1)
    out = (x * 255).astype(np.uint8)
    hsv = cv2.cvtColor(out, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 1.10, 0, 255)
    out = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
    # 6. vignette
    vkey = ("vig", h, w)
    if vkey not in _FOG_CACHE:
        Y, X = np.ogrid[:h, :w]
        r = np.sqrt(((X - w / 2) / (w / 2)) ** 2 + ((Y - h / 2) / (h / 2)) ** 2)
        _FOG_CACHE[vkey] = np.clip(
            1 - 0.15 * np.clip(r - 0.6, 0, None) ** 1.5, 0, 1)[..., None].astype(np.float32)
    return (out * _FOG_CACHE[vkey]).astype(np.uint8)


def dark_panel(frame, rect, alpha=.92, radius=0):
    x1, y1, x2, y2 = rect
    layer = frame.copy()
    if radius:
        cv2.rectangle(layer, (x1 + radius, y1), (x2 - radius, y2), BG, -1)
        cv2.rectangle(layer, (x1, y1 + radius), (x2, y2 - radius), BG, -1)
        cv2.circle(layer, (x1 + radius, y1 + radius), radius, BG, -1)
        cv2.circle(layer, (x2 - radius, y1 + radius), radius, BG, -1)
        cv2.circle(layer, (x1 + radius, y2 - radius), radius, BG, -1)
        cv2.circle(layer, (x2 - radius, y2 - radius), radius, BG, -1)
    else:
        cv2.rectangle(layer, (x1, y1), (x2, y2), BG, -1)
    cv2.addWeighted(layer, alpha, frame, 1 - alpha, 0, frame)


def contain(image, width=W, height=H, pad=0):
    canvas = np.full((height, width, 3), BG, dtype=np.uint8)
    ih, iw = image.shape[:2]
    scale = min((width - 2 * pad) / iw, (height - 2 * pad) / ih)
    nw, nh = int(iw * scale), int(ih * scale)
    resized = cv2.resize(image, (nw, nh), interpolation=cv2.INTER_AREA)
    x, y = (width - nw) // 2, (height - nh) // 2
    canvas[y:y + nh, x:x + nw] = resized
    return canvas


def cover(image, width=W, height=H):
    ih, iw = image.shape[:2]
    scale = max(width / iw, height / ih)
    nw, nh = int(iw * scale), int(ih * scale)
    resized = cv2.resize(image, (nw, nh), interpolation=cv2.INTER_LANCZOS4)
    x, y = (nw - width) // 2, (nh - height) // 2
    return resized[y:y + height, x:x + width].copy()


def fade(frame, local_idx, total, fade_frames=9):
    alpha = 1.0
    if local_idx < fade_frames:
        alpha = local_idx / max(1, fade_frames - 1)
    elif local_idx >= total - fade_frames:
        alpha = (total - 1 - local_idx) / max(1, fade_frames - 1)
    if alpha >= .999:
        return frame
    bg = np.full_like(frame, BG)
    return cv2.addWeighted(frame, max(0, alpha), bg, 1 - max(0, alpha), 0)


def cinematic_overlay(frame, idx):
    t = idx / FPS
    if t < 4.0:
        kicker = "BRINEWATCH"
        headline = "Find the outfall. Map the plume."
        sub = "A repeatable robotic mission for brine screening"
        accent = TEAL
    elif t < 9.0:
        kicker = "LOCATE"
        headline = "Keep the structure in view"
        sub = "Omniscan 450 FS forward-looking imaging sonar"
        accent = CYAN
    elif t < 15.0:
        kicker = "INSPECT"
        headline = "Follow the pipe to the diffuser"
        sub = "A stable approach preserves the accepted geometry"
        accent = TEAL
    else:
        kicker = "SENSE"
        headline = "Build evidence around risers and nozzles"
        sub = "Planned hardware gate: calibrated CT payload"
        accent = WARM

    # Compact top-right caption: readable without obscuring the approach or structure.
    dark_panel(frame, (1180, 44, 1868, 208), alpha=.88, radius=16)
    inner = 1868 - 1210 - 26
    text_block(frame, [
        (kicker, (1210, 82), fit_size(kicker, .52, True, inner), accent, 2),
        (headline, (1210, 129), fit_size(headline, .80, True, inner), WHITE, 2),
        (sub, (1210, 177), fit_size(sub, .54, False, inner), MUTED, 1),
    ])


def stage_title(frame, kicker, headline, sub=None, accent=TEAL):
    # Opaque band deliberately hides any pre-existing figure title.
    cv2.rectangle(frame, (0, 0), (W, 240), BG, -1)
    entries = [
        (kicker, (82, 68), .64, accent, 2),
        (headline, (82, 136), 1.20, WHITE, 2),
    ]
    if sub:
        entries.append((sub, (84, 190), .60, MUTED, 1))
    text_block(frame, entries)


def load_image(path):
    image = cv2.imread(str(path))
    if image is None:
        raise FileNotFoundError(path)
    return image


def autotrim(image, tol=14, pad=26):
    """Trim uniform border margins (background-coloured) so the artwork can be
    shown as large as possible. Keeps a small aesthetic padding."""
    ref = image[2, 2].astype(np.int16)
    diff = np.abs(image.astype(np.int16) - ref).sum(axis=2)
    mask = diff > tol
    if not mask.any():
        return image
    ys, xs = np.where(mask)
    y0, y1 = max(0, ys.min() - pad), min(image.shape[0], ys.max() + pad)
    x0, x1 = max(0, xs.min() - pad), min(image.shape[1], xs.max() + pad)
    return image[y0:y1, x0:x1]


def write_static(writer, image_path, seconds, kicker, headline, sub, scenes,
                 frame_cursor, accent=TEAL):
    source = autotrim(load_image(image_path))
    # Fit the artwork entirely BELOW the opaque title band: nothing from the
    # source figure is ever covered or clipped by the headline strip.
    top_band, gap, bottom_margin = 240, 14, 18
    art_h = H - top_band - gap - bottom_margin
    inner = contain(source, W, art_h, pad=0)
    base = np.full((H, W, 3), BG, dtype=np.uint8)
    base[top_band + gap:top_band + gap + art_h] = inner
    n = int(seconds * FPS)
    for i in range(n):
        frame = base.copy()
        stage_title(frame, kicker, headline, sub, accent)
        writer.write(fade(frame, i, n))
    scenes.append({"name": kicker.lower().replace(" ", "_"),
                   "start_s": frame_cursor / FPS,
                   "end_s": (frame_cursor + n) / FPS,
                   "motion": "fixed image; fade only"})
    return frame_cursor + n


def write_3d(writer, source_path, seconds, scenes, frame_cursor):
    cap = cv2.VideoCapture(str(source_path))
    if not cap.isOpened():
        raise FileNotFoundError(source_path)
    total_source = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    n = int(seconds * FPS)
    indices = np.linspace(0, max(0, total_source - 1), n).astype(int)
    wanted = {int(value): [] for value in indices}
    for out_idx, src_idx in enumerate(indices):
        wanted[int(src_idx)].append(out_idx)
    rendered = [None] * n
    src_idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if src_idx in wanted:
            base = contain(frame)
            # Remove the dense original title and metrics while retaining the fixed 3-D view.
            cv2.rectangle(base, (0, 0), (W, 240), BG, -1)
            cv2.rectangle(base, (1510, 240), (W, H), BG, -1)
            stage_title(base, "RECONSTRUCT", "Four layers become one 3-D plume",
                        "Samples, altitude bands and confidence appear progressively", CORAL)
            dark_panel(base, (1535, 350, 1850, 755), alpha=.96, radius=18)
            text_block(base, [
                ("ONE MODEL", (1580, 420), .58, CORAL, 2),
                ("4 altitude bands", (1580, 488), .76, WHITE, 2),
                ("trajectory", (1580, 557), .72, WHITE, 2),
                ("threshold surface", (1580, 626), .72, WHITE, 2),
                ("visible confidence", (1580, 695), .72, WHITE, 2),
            ])
            for out_idx in wanted[src_idx]:
                rendered[out_idx] = base.copy()
        src_idx += 1
    cap.release()
    last = np.full((H, W, 3), BG, np.uint8)
    for i, frame in enumerate(rendered):
        if frame is None:
            frame = last.copy()
        else:
            last = frame.copy()
        writer.write(fade(frame, i, n))
    scenes.append({"name": "progressive_3d", "start_s": frame_cursor / FPS,
                   "end_s": (frame_cursor + n) / FPS,
                   "motion": "fixed camera; progressive scientific reconstruction"})
    return frame_cursor + n


def final_card(hero, idx, total):
    frame = cover(hero)
    overlay = np.full_like(frame, BG)
    frame = cv2.addWeighted(overlay, .76, frame, .24, 0)
    dark_panel(frame, (74, 108, 1455, 932), alpha=.58, radius=28)
    text_block(frame, [
        ("BRINEWATCH", (125, 214), .80, TEAL, 2),
        ("From underwater inspection to", (123, 332), 1.48, WHITE, 2),
        ("actionable environmental evidence.", (123, 408), 1.48, WHITE, 2),
        ("CURRENT PROTOTYPE", (127, 525), .58, TEAL, 2),
        ("Sonar localisation  |  collision-free HoloOcean mission",
         (127, 582), .76, WHITE, 2),
        ("Adaptive 2-D/3-D maps  |  simulation-based digital twin",
         (127, 632), .76, WHITE, 2),
        ("NEXT", (127, 738), .58, WARM, 2),
        ("On-site sea validation with a calibrated CT payload.",
         (127, 804), .86, WHITE, 2),
    ])
    return fade(frame, idx, total, fade_frames=12)


def decode_frames(path):
    cap = cv2.VideoCapture(str(path))
    frames = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frames.append(frame)
    cap.release()
    return frames


def build_short(main_path, short_path, scenes, crf=10, preset="medium"):
    cap = cv2.VideoCapture(str(main_path))
    writer = H264Writer(short_path, crf=crf, preset=preset)
    # 0-11 s underwater, then shortened result/twin/close segments.
    ranges = [
        (0.0, 11.0),
        (scenes[1]["start_s"], min(scenes[1]["start_s"] + 2.8, scenes[1]["end_s"])),
        (scenes[2]["start_s"], min(scenes[2]["start_s"] + 2.8, scenes[2]["end_s"])),
        (scenes[3]["start_s"], min(scenes[3]["start_s"] + 4.5, scenes[3]["end_s"])),
        (scenes[4]["start_s"], min(scenes[4]["start_s"] + 3.4, scenes[4]["end_s"])),
        (scenes[5]["start_s"], scenes[5]["end_s"]),
    ]
    frame_ranges = [(int(a * FPS), int(b * FPS)) for a, b in ranges]
    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if any(a <= idx < b for a, b in frame_ranges):
            writer.write(frame)
        idx += 1
    cap.release()
    writer.release()
    return sum(b - a for a, b in frame_ranges)


def build_contact_and_keys(final_path, out, scenes, total_frames):
    contact_indices = np.linspace(0, total_frames - 1, 12).astype(int)
    lookup = {int(value): i for i, value in enumerate(contact_indices)}
    contacts = [None] * len(contact_indices)
    key_targets = {
        min(total_frames - 1, int((scene["start_s"] + .45) * FPS)): (i, scene)
        for i, scene in enumerate(scenes)
    }
    cap = cv2.VideoCapture(str(final_path))
    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx in lookup:
            contacts[lookup[idx]] = frame.copy()
        if idx in key_targets:
            order, scene = key_targets[idx]
            cv2.imwrite(str(out / f"keyframe_{order + 1:02d}_{scene['name']}.jpg"), frame,
                        [cv2.IMWRITE_JPEG_QUALITY, 94])
        idx += 1
    cap.release()
    sheet = np.full((270 * 3, 480 * 4, 3), 8, dtype=np.uint8)
    for i, frame in enumerate(contacts):
        if frame is None:
            continue
        row, col = divmod(i, 4)
        sheet[row * 270:(row + 1) * 270, col * 480:(col + 1) * 480] = cv2.resize(
            frame, (480, 270), interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(out / "BrineWatch_PFH2026_Public_contact_sheet.jpg"), sheet,
                [cv2.IMWRITE_JPEG_QUALITY, 93])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--cinematic",
        default=r"C:\bwrt\bwp26-cin1\outputs\cinematic_1080p\BrineWatch_HoloOcean_Continuous_1080p_Source.mp4",
    )
    ap.add_argument("--assets", default=str(ROOT / "output" / "redesign" / "assets"))
    ap.add_argument("--source-assets", default=str(ROOT / "output" / "fasttrack" / "assets"))
    ap.add_argument(
        "--plume-video",
        default=str(ROOT / "output" / "fasttrack" / "video_sources" /
                    "BrineWatch_3D_Plume_Progressive_1080p.mp4"),
    )
    ap.add_argument("--out", default=str(ROOT / "output" / "redesign" / "video"))
    ap.add_argument("--crf", type=int, default=10,
                    help="H.264 quality: lower is better; 10 is the high-quality master")
    ap.add_argument("--preset", default="medium",
                    help="libx264 encoding preset")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    assets = Path(args.assets)
    source_assets = Path(args.source_assets)
    final = out / "BrineWatch_PFH2026_Public_1080p.mp4"
    writer = H264Writer(final, crf=args.crf, preset=args.preset)

    scenes = []
    cursor = 0
    cap = cv2.VideoCapture(args.cinematic)
    if not cap.isOpened():
        raise FileNotFoundError(args.cinematic)
    cinematic_count = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame = grade_underwater(frame)
        cinematic_overlay(frame, cinematic_count)
        writer.write(frame)
        cinematic_count += 1
    cap.release()
    scenes.append({"name": "continuous_holoocean", "start_s": 0.0,
                   "end_s": cinematic_count / FPS,
                   "motion": "625 consecutive genuine custom-HoloOcean RGB frames"})
    cursor += cinematic_count

    cursor = write_static(
        writer, assets / "result_sonar.png", 3.8,
        "LOCATE", "Two sonar views agree on the outfall",
        "2.35 m scored centre error | no oracle input", scenes, cursor, TEAL,
    )
    cursor = write_static(
        writer, assets / "result_2d.png", 3.8,
        "ADAPT + RECONSTRUCT", "The route resolves the plume boundary",
        "0.900 boundary IoU | correct conclusive screen", scenes, cursor, WARM,
    )
    cursor = write_3d(writer, Path(args.plume_video), 6.0, scenes, cursor)
    cursor = write_static(
        writer, assets / "digital_twin_simple.png", 4.3,
        "ACT", "The twin remembers the site",
        "Current map + uncertainty + route + history + next action", scenes, cursor, CYAN,
    )

    hero = load_image(source_assets / "hero_structure.png")
    close_n = int(5.2 * FPS)
    close_start = cursor
    for i in range(close_n):
        writer.write(final_card(hero, i, close_n))
    cursor += close_n
    scenes.append({"name": "closing", "start_s": close_start / FPS,
                   "end_s": cursor / FPS, "motion": "fixed background; fade only"})
    writer.release()

    short = out / "BrineWatch_PFH2026_Public_Short_1080p.mp4"
    short_frames = build_short(final, short, scenes, args.crf, args.preset)
    build_contact_and_keys(final, out, scenes, cursor)

    manifest = {
        "upload_this_video": final.name,
        "optional_short_cut": short.name,
        "resolution": [W, H],
        "fps": FPS,
        "duration_s": round(cursor / FPS, 3),
        "short_duration_s": round(short_frames / FPS, 3),
        "codec": "H.264 High Profile / yuv420p (libx264)",
        "encoding": {"crf": args.crf, "preset": args.preset,
                     "faststart": True},
        "cinematic_caption": {
            "position": "top-right",
            "rectangle_px": [1180, 44, 1868, 208],
            "frame_coverage_percent": 5.4,
        },
        "continuous_holoocean": {
            "frames": cinematic_count,
            "duration_s": round(cinematic_count / FPS, 3),
            "source": str(Path(args.cinematic)),
            "ken_burns_or_static_substitution": False,
            "camera_path": "dedicated cinematic, not telemetry-synchronised replay",
        },
        "scientific_pan_or_zoom": False,
        "scientific_transition": "fixed frame with short fade/cut only",
        "scenes": scenes,
        "public_story": ["continuous mission", "sonar", "2-D map", "3-D volume",
                         "digital twin", "next validation gate"],
    }
    (out / "PUBLIC_VIDEO_MANIFEST.json").write_text(json.dumps(manifest, indent=2),
                                                       encoding="utf-8")
    print(f"[public-video] {final} ({manifest['duration_s']:.1f}s)")
    print(f"[public-video] {short} ({manifest['short_duration_s']:.1f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

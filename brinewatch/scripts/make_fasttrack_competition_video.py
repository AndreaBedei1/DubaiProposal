"""Assemble the final Full-HD BrineWatch competition film with OpenCV."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
W, H, FPS = 1920, 1080, 30
BG = (29, 23, 6)          # BGR #06171d
TEAL = (191, 212, 45)     # BGR #2dd4bf
WHITE = (252, 251, 244)
MUTED = (188, 183, 157)
RED = (133, 113, 251)


def grade_underwater(frame):
    x = frame.astype(np.float32) / 255.0
    x = np.clip((x - .5) * 1.23 + .43, 0, 1)
    x = np.power(x, 1.04)
    out = np.uint8(np.clip(x * 255, 0, 255))
    hsv = cv2.cvtColor(out, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 1.08, 0, 255)
    out = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
    blur = cv2.GaussianBlur(out, (0, 0), 1.25)
    return cv2.addWeighted(out, 1.22, blur, -.22, 0)


def cover(image, width=W, height=H, scale=1.0, centre=(.5, .5)):
    h, w = image.shape[:2]
    base = max(width / w, height / h) * scale
    nw, nh = max(width, int(w * base)), max(height, int(h * base))
    resized = cv2.resize(image, (nw, nh), interpolation=cv2.INTER_LANCZOS4)
    cx = int(np.clip(centre[0], 0, 1) * max(0, nw - width))
    cy = int(np.clip(centre[1], 0, 1) * max(0, nh - height))
    return resized[cy:cy + height, cx:cx + width].copy()


def text(frame, value, xy, size, color=WHITE, thickness=2):
    cv2.putText(frame, value, xy, cv2.FONT_HERSHEY_SIMPLEX, size, color,
                thickness, cv2.LINE_AA)


def banner(frame, kicker, title, subtitle=""):
    layer = frame.copy()
    cv2.rectangle(layer, (0, 0), (W, 215), BG, -1)
    # Keep section titles legible over figures that already contain a header.
    cv2.addWeighted(layer, .96, frame, .04, 0, frame)
    text(frame, kicker.upper(), (80, 70), .65, TEAL, 2)
    text(frame, title, (80, 140), 1.35, WHITE, 3)
    if subtitle:
        text(frame, subtitle, (82, 190), .58, MUTED, 1)


def cinematic_caption(frame, phase, idx):
    mapping = {
        "site_and_descent": ("SITE + DESCENT", "Structure visible from the first second"),
        "early_acquisition": ("EARLY ACQUISITION", "A stable camera keeps the outfall in view"),
        "pipeline_approach": ("APPROACH", "Follow the main pipe toward the diffuser"),
        "follow_pipeline": ("INSPECT", "Controlled pass along the accepted structure"),
        "riser_inspection": ("RISERS", "Close-range infrastructure and plume-source context"),
        "lateral_pass": ("LATERAL PASS", "Read the multiport geometry from another aspect"),
        "close_nozzles": ("SENSE", "Omniscan 450 FS concept + planned CT payload"),
        "cross_over": ("ONE MISSION", "Infrastructure inspection + plume screening"),
    }
    kicker, subtitle = mapping.get(phase, ("HOLOOCEAN", "Continuous simulated capture"))
    layer = frame.copy()
    cv2.rectangle(layer, (55, 815), (1035, 1015), BG, -1)
    cv2.addWeighted(layer, .76, frame, .24, 0, frame)
    text(frame, kicker, (90, 875), .78, TEAL, 2)
    text(frame, subtitle, (90, 944), .85, WHITE, 2)
    text(frame, "GENUINE CONTINUOUS CUSTOM-HOLOOCEAN RGB | 1920 x 1080 | 30 fps",
         (90, 990), .42, MUTED, 1)
    if idx < 75:
        text(frame, "BRINEWATCH", (80, 105), .72, TEAL, 2)
        text(frame, "More informative spatial evidence under constrained survey time",
             (80, 172), 1.03, WHITE, 2)


def read_image(path):
    image = cv2.imread(str(path))
    if image is None:
        raise FileNotFoundError(path)
    return image


def add_static_stage(writer, image_path, seconds, kicker, title, subtitle,
                     zoom=(1.0, 1.025), centre0=(.5, .5), centre1=(.5, .5),
                     collected=None):
    image = read_image(image_path)
    n = int(round(seconds * FPS))
    for i in range(n):
        u = i / max(1, n - 1)
        s = zoom[0] * (1 - u) + zoom[1] * u
        centre = (centre0[0] * (1 - u) + centre1[0] * u,
                  centre0[1] * (1 - u) + centre1[1] * u)
        frame = cover(image, scale=s, centre=centre)
        banner(frame, kicker, title, subtitle)
        writer.write(frame)
        if collected is not None:
            collected.append(frame)
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cinematic", default=r"C:\bwrt\bwp26-cin1\outputs\cinematic_1080p\BrineWatch_HoloOcean_Continuous_1080p_Source.mp4")
    ap.add_argument("--camera-log", default=r"C:\bwrt\bwp26-cin1\outputs\cinematic_1080p\camera_pose_log.json")
    ap.add_argument("--assets", default=str(ROOT / "output" / "fasttrack" / "assets"))
    ap.add_argument("--plume-video", default=str(ROOT / "output" / "fasttrack" /
                    "video_sources" / "BrineWatch_3D_Plume_Progressive_1080p.mp4"))
    ap.add_argument("--out", default=str(ROOT / "output" / "fasttrack" / "video"))
    args = ap.parse_args()
    assets, out = Path(args.assets), Path(args.out)
    sources = ROOT / "output" / "fasttrack" / "video_sources"
    out.mkdir(parents=True, exist_ok=True)
    sources.mkdir(parents=True, exist_ok=True)
    final = out / "BrineWatch_PFH2026_Final_1080p.mp4"
    graded = sources / "BrineWatch_HoloOcean_Continuous_1080p_Graded.mp4"
    writer = cv2.VideoWriter(str(final), cv2.VideoWriter_fourcc(*"mp4v"),
                             FPS, (W, H))
    graded_writer = cv2.VideoWriter(str(graded), cv2.VideoWriter_fourcc(*"mp4v"),
                                    FPS, (W, H))
    if not writer.isOpened() or not graded_writer.isOpened():
        raise RuntimeError("could not open final MP4 writer")
    scenes = []
    start_frame = 0

    camera_log = json.loads(Path(args.camera_log).read_text(encoding="utf-8"))
    cap = cv2.VideoCapture(str(args.cinematic))
    idx = 0
    while True:
        ok, raw = cap.read()
        if not ok:
            break
        if raw.shape[1::-1] != (W, H):
            raw = cv2.resize(raw, (W, H), interpolation=cv2.INTER_LANCZOS4)
        frame = grade_underwater(raw)
        phase = camera_log[min(idx, len(camera_log) - 1)]["phase"]
        cinematic_caption(frame, phase, idx)
        graded_writer.write(frame)
        writer.write(frame)
        idx += 1
    cap.release()
    graded_writer.release()
    scenes.append({"name": "continuous_holoocean_inspection",
                   "start_s": start_frame / FPS, "end_s": idx / FPS,
                   "source": str(Path(args.cinematic).resolve())})
    start_frame = idx

    n = add_static_stage(
        writer, assets / "sonar_localization.png", 4.3,
        "Locate | Omniscan 450 FS concept",
        "Two search radii confirm the outfall",
        "2.35 m centre error | 1.67 m posterior radius | 5/5 non-fallback prior trials",
        zoom=(1.0, 1.018), centre0=(.48, .5), centre1=(.52, .5),
        collected=None)
    scenes.append({"name": "sonar_localization", "start_s": start_frame / FPS,
                   "end_s": (start_frame + n) / FPS})
    start_frame += n
    n = add_static_stage(
        writer, assets / "mission_reconstruction.png", 4.2,
        "Sense -> Adapt -> Reconstruct -> Act",
        "The adaptive path resolves the plume boundary",
        "Flagship demo: 0.342 PSU RMSE | F1 0.947 | correct POSSIBLE EXCEEDANCE",
        zoom=(1.0, 1.014), collected=None)
    scenes.append({"name": "adaptive_survey", "start_s": start_frame / FPS,
                   "end_s": (start_frame + n) / FPS})
    start_frame += n

    plume = cv2.VideoCapture(str(args.plume_video))
    plume_n = 0
    while True:
        ok, frame = plume.read()
        if not ok:
            break
        if frame.shape[1::-1] != (W, H):
            frame = cv2.resize(frame, (W, H), interpolation=cv2.INTER_LANCZOS4)
        writer.write(frame)
        plume_n += 1
    plume.release()
    scenes.append({"name": "progressive_3d_reconstruction",
                   "start_s": start_frame / FPS,
                   "end_s": (start_frame + plume_n) / FPS,
                   "source": str(Path(args.plume_video).resolve())})
    start_frame += plume_n

    n = add_static_stage(
        writer, assets / "digital_twin_dashboard.png", 4.7,
        "Digital twin",
        "Each mission updates one operational picture",
        "Latest map + uncertainty + route + sonar anchor + verdict + mission history",
        zoom=(1.0, 1.016), collected=None)
    scenes.append({"name": "digital_twin", "start_s": start_frame / FPS,
                   "end_s": (start_frame + n) / FPS})
    start_frame += n
    n = add_static_stage(
        writer, assets / "benchmark_comparison.png", 4.0,
        "Equal evidence budget | 8 seeds",
        "Adaptive sampling concentrates effort where it matters",
        "48 readings | ~300 m | correct POSSIBLE EXCEEDANCE in 8/8 adaptive runs",
        zoom=(1.0, 1.012), collected=None)
    scenes.append({"name": "comparison", "start_s": start_frame / FPS,
                   "end_s": (start_frame + n) / FPS})
    start_frame += n

    hero = read_image(assets / "hero_structure.png")
    n = 5 * FPS
    for i in range(n):
        u = i / max(1, n - 1)
        frame = cover(hero, scale=1.0 + .018 * u, centre=(.5, .53))
        layer = frame.copy()
        cv2.rectangle(layer, (0, 0), (W, H), BG, -1)
        cv2.addWeighted(layer, .70, frame, .30, 0, frame)
        text(frame, "NEXT", (90, 210), .75, TEAL, 2)
        text(frame, "Integrate the CT payload.", (90, 315), 1.55, WHITE, 3)
        text(frame, "Validate in controlled water.", (90, 405), 1.55, WHITE, 3)
        text(frame, "Then target certified sampling where the evidence says it matters.",
             (92, 500), .82, MUTED, 2)
        text(frame, "BRINEWATCH", (90, 875), .85, TEAL, 2)
        text(frame, "Same-day spatial evidence. Repeatable site history. Focused follow-up.",
             (90, 950), .92, WHITE, 2)
        writer.write(frame)
    scenes.append({"name": "closing", "start_s": start_frame / FPS,
                   "end_s": (start_frame + n) / FPS})
    total_frames = start_frame + n
    writer.release()

    # Short cut: first 12 s of genuine capture + sonar + 3-D + dashboard + close.
    short = out / "BrineWatch_PFH2026_Short_1080p.mp4"
    sw = cv2.VideoWriter(str(short), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    ranges = [(0, 12),
              (scenes[1]["start_s"], scenes[1]["end_s"]),
              (scenes[3]["start_s"], scenes[3]["end_s"]),
              (scenes[4]["start_s"], scenes[4]["end_s"]),
              (scenes[-1]["start_s"], scenes[-1]["end_s"])]
    short_ranges = [(int(a * FPS), int(b * FPS)) for a, b in ranges]

    # One decode pass builds the short cut, contact sheet and scene keyframes
    # without retaining the Full-HD film in memory.
    contact_indices = np.linspace(0, total_frames - 1, 12).astype(int)
    contact_lookup = {int(value): i for i, value in enumerate(contact_indices)}
    contacts = [None] * len(contact_indices)
    key_targets = {
        min(total_frames - 1, int((scene["start_s"] + .4) * FPS)): (i, scene)
        for i, scene in enumerate(scenes)
    }
    source = cv2.VideoCapture(str(final))
    frame_idx = 0
    while True:
        ok, frame = source.read()
        if not ok:
            break
        if any(a <= frame_idx < b for a, b in short_ranges):
            sw.write(frame)
        if frame_idx in contact_lookup:
            contacts[contact_lookup[frame_idx]] = frame.copy()
        if frame_idx in key_targets:
            i, scene = key_targets[frame_idx]
            cv2.imwrite(str(out / f"keyframe_{i + 1:02d}_{scene['name']}.jpg"),
                        frame, [cv2.IMWRITE_JPEG_QUALITY, 94])
        frame_idx += 1
    source.release()
    sw.release()

    # Contact sheet from 12 representative final frames.
    sheet = np.full((270 * 3, 480 * 4, 3), 8, dtype=np.uint8)
    for i, frame in enumerate(contacts):
        y, x = divmod(i, 4)
        if frame is None:
            continue
        thumb = cv2.resize(frame, (480, 270), interpolation=cv2.INTER_AREA)
        sheet[y * 270:(y + 1) * 270, x * 480:(x + 1) * 480] = thumb
    cv2.imwrite(str(out / "BrineWatch_PFH2026_Final_contact_sheet.jpg"), sheet,
                [cv2.IMWRITE_JPEG_QUALITY, 92])
    manifest = {
        "upload_this_video": final.name,
        "optional_short_cut": short.name,
        "resolution": [W, H], "fps": FPS,
        "duration_s": round(total_frames / FPS, 3),
        "codec": "MPEG-4 Part 2 in MP4 (OpenCV mp4v)",
        "scenes": scenes,
        "continuous_capture": {
            "duration_s": round(idx / FPS, 3),
            "genuine_holoocean_frames": idx,
            "ken_burns_or_static_substitution": False,
            "camera_path": "dedicated cinematic, not telemetry-synchronised replay",
            "grade": "contrast/saturation tone grade only; native engine haze retained",
        },
        "3d_animation": {
            "duration_s": round(plume_n / FPS, 3),
            "type": "progressive reveal of samples, bands, final GP volume and uncertainty",
        },
        "claims_disclosure": ("Cinematic capture and science results share the "
                              "same simulated scene context but are not a "
                              "telemetry-synchronised replay."),
    }
    (out / "VIDEO_MANIFEST.json").write_text(json.dumps(manifest, indent=2),
                                              encoding="utf-8")
    print(f"[competition-video] final {final} ({manifest['duration_s']:.1f} s)")
    print(f"[competition-video] short {short}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

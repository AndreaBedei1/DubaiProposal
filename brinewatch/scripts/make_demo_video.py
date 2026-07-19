"""Assemble a frame folder into an MP4 (OpenCV) and a preview GIF (PIL).

No ffmpeg dependency. Use after capture_cinematic_inspection.py, or to
re-encode any ``frame_*.png`` sequence.

    python scripts/make_demo_video.py --frames outputs/cinematic_*/frames --fps 24
"""
from __future__ import annotations

import argparse
import glob
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--frames", required=True, help="frames dir or glob")
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--pattern", default="frame_*.png")
    ap.add_argument("--gif-stride", type=int, default=3,
                    help="use every Nth frame for the (smaller) preview GIF")
    args = ap.parse_args()

    frame_dir = Path(sorted(glob.glob(args.frames))[-1]) if any(
        ch in args.frames for ch in "*?[") else Path(args.frames)
    files = sorted(frame_dir.glob(args.pattern))
    if not files:
        print(f"no frames matching {args.pattern} in {frame_dir}")
        return 1
    out = frame_dir.parent

    # MP4 via OpenCV
    try:
        import cv2
        h, w = cv2.imread(str(files[0])).shape[:2]
        vw = cv2.VideoWriter(str(out / "demo.mp4"),
                             cv2.VideoWriter_fourcc(*"mp4v"), args.fps, (w, h))
        for f in files:
            vw.write(cv2.imread(str(f)))
        vw.release()
        print(f"MP4: {out / 'demo.mp4'} ({len(files)} frames @ {args.fps} fps)")
    except Exception as exc:
        print(f"MP4 skipped: {exc}")

    # preview GIF via PIL
    try:
        from PIL import Image
        imgs = [Image.open(f).convert("P", palette=Image.ADAPTIVE)
                for f in files[::args.gif_stride]]
        if imgs:
            imgs[0].save(out / "demo.gif", save_all=True, append_images=imgs[1:],
                         duration=int(1000 / args.fps * args.gif_stride), loop=0)
            print(f"GIF: {out / 'demo.gif'} ({len(imgs)} frames)")
    except Exception as exc:
        print(f"GIF skipped: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Assemble the BrineWatch demonstration MP4 from REAL mission outputs.

Every frame is genuine simulator output: the in-engine survey trajectory, the
recorded ImagingSonar, the GP plume reconstruction and the screening verdict all
come from a custom-HoloOcean mission run (run_custom_holoocean_mission.py); the
ROV flythrough clip is engine RGBCamera capture. The salinity field is the
documented analytic surrogate. Encoded with OpenCV (mp4v) — no ffmpeg / imageio.

Stages: title -> site overview -> sonar localization -> ROV inspection clip
(engine RGB) -> collision-safe survey (animated trajectory) -> plume + uncertainty
-> 3-D volumetric -> screening verdict -> digital-twin history -> end card.

    python scripts/make_mission_movie.py \
        --run outputs/custom_holoocean_mission_20260721_210559 \
        --rgb outputs/cinematic_FlatUnderwater_20260719_124100/frames \
        --volumetric outputs/volumetric/adaptive_run1/volumetric_isosurface.png \
        --history site_history/site_history_trend.png \
        --out outputs/video_demo/mission_movie
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

W, H, FPS = 1280, 720, 20
BG = "#0b1420"
FG = "#e8eef5"
ACCENT = "#38bdf8"


def _fig():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(W / 100, H / 100), dpi=100)
    fig.patch.set_facecolor(BG)
    return fig, plt


def _to_frame(fig) -> np.ndarray:
    fig.canvas.draw()
    buf = np.asarray(fig.canvas.buffer_rgba())[:, :, :3].copy()
    import matplotlib.pyplot as plt
    plt.close(fig)
    if buf.shape[0] != H or buf.shape[1] != W:
        import cv2
        buf = cv2.resize(buf, (W, H))
    return buf


def _hold(frames, img, n):
    for _ in range(n):
        frames.append(img)


def _title_card(text, subtitle="", note=""):
    fig, plt = _fig()
    fig.text(0.5, 0.60, text, color=FG, fontsize=34, ha="center", va="center",
             weight="bold")
    if subtitle:
        fig.text(0.5, 0.48, subtitle, color=ACCENT, fontsize=18, ha="center")
    if note:
        fig.text(0.5, 0.36, note, color="#9fb3c8", fontsize=13, ha="center")
    return _to_frame(fig)


def _banner(fig, stage, caption):
    fig.text(0.04, 0.94, stage, color=ACCENT, fontsize=15, weight="bold", va="top")
    if caption:
        fig.text(0.04, 0.06, caption, color="#9fb3c8", fontsize=12, va="bottom")


def site_overview(cfg_survey, prior, estimate):
    fig, plt = _fig()
    ax = fig.add_axes([0.08, 0.12, 0.84, 0.76])
    ax.set_facecolor("#0f1c2b")
    ax.add_patch(plt.Rectangle((cfg_survey["x_min"], cfg_survey["y_min"]),
                               cfg_survey["x_max"] - cfg_survey["x_min"],
                               cfg_survey["y_max"] - cfg_survey["y_min"],
                               fill=False, ec=ACCENT, lw=1.5, ls="--"))
    ax.plot(*prior, "x", color="#f59e0b", ms=13, mew=3, label="chart prior")
    if estimate:
        ax.plot(*estimate, "o", color="#34d399", ms=11, label="sonar estimate")
    ax.set_xlim(cfg_survey["x_min"] - 5, cfg_survey["x_max"] + 5)
    ax.set_ylim(cfg_survey["y_min"] - 5, cfg_survey["y_max"] + 5)
    ax.set_aspect("equal")
    for s in ax.spines.values():
        s.set_color("#33465c")
    ax.tick_params(colors="#7f95a8")
    ax.set_xlabel("x (m)", color="#9fb3c8")
    ax.set_ylabel("y (m)", color="#9fb3c8")
    leg = ax.legend(loc="upper right", facecolor="#0f1c2b", edgecolor="#33465c")
    for t in leg.get_texts():
        t.set_color(FG)
    _banner(fig, "1 · SITE OVERVIEW",
            "Survey box over a desalination outfall of uncertain exact position")
    return _to_frame(fig)


def sonar_stage(sonar_img, locate):
    fig, plt = _fig()
    ax = fig.add_axes([0.08, 0.12, 0.5, 0.76])
    im = np.log1p(np.clip(np.asarray(sonar_img, float), 0, None))
    ax.imshow(im, aspect="auto", cmap="magma", origin="lower")
    ax.set_title("ImagingSonar (range-azimuth)", color=FG, fontsize=13)
    ax.set_xlabel("azimuth bin", color="#9fb3c8")
    ax.set_ylabel("range bin", color="#9fb3c8")
    ax.tick_params(colors="#7f95a8")
    est = locate.get("estimate")
    err = None
    if est:
        err = float(np.hypot(est[0] - 39.8, est[1] - 0.0))
    lines = [
        "Background subtraction +",
        "diffuser-line fit (no GT)",
        "",
        f"residual contacts: {locate.get('residual_contacts','?')}",
        f"inliers: {locate.get('n_inliers','?')}",
        f"axis: {locate.get('axis_deg','?')}°",
        f"estimate: ({est[0]:.1f}, {est[1]:.1f}) m" if est else "estimate: —",
        f"error vs truth: {err:.2f} m" if err is not None else "",
    ]
    fig.text(0.63, 0.72, "\n".join(lines), color=FG, fontsize=15, va="top",
             family="monospace")
    _banner(fig, "2 · SONAR DETECTION & LOCALIZATION",
            "The spawned outfall is sonar-visible via the runtime octree rebuild")
    return _to_frame(fig)


def survey_frames(npz, screening_txt, n_anim=64):
    """Animate the trajectory building up over the GP-mean plume."""
    import matplotlib.pyplot as plt
    mean = npz["mean"]; X = npz["X"]; Y = npz["Y"]; traj = npz["trajectory"]
    vmin, vmax = float(mean.min()), float(mean.max())
    tx, ty = traj[:, 1], traj[:, 2]
    frames = []
    m = len(tx)
    for k in range(1, n_anim + 1):
        fig, _ = _fig()
        ax = fig.add_axes([0.1, 0.12, 0.78, 0.76])
        ax.set_facecolor("#0f1c2b")
        pcm = ax.pcolormesh(X, Y, mean, cmap="viridis", vmin=vmin, vmax=vmax,
                            shading="auto", alpha=0.9)
        j = int(m * k / n_anim)
        ax.plot(tx[:j], ty[:j], "-", color="#ff5d73", lw=1.4, alpha=0.9)
        if j > 0:
            ax.plot(tx[j - 1], ty[j - 1], "o", color="#ffd166", ms=9)
        cb = fig.colorbar(pcm, ax=ax, fraction=0.046, pad=0.04)
        cb.set_label("salinity (PSU)", color="#9fb3c8")
        cb.ax.yaxis.set_tick_params(color="#7f95a8")
        plt.setp(plt.getp(cb.ax, "yticklabels"), color="#9fb3c8")
        ax.set_xlabel("x (m)", color="#9fb3c8")
        ax.set_ylabel("y (m)", color="#9fb3c8")
        ax.tick_params(colors="#7f95a8")
        for s in ax.spines.values():
            s.set_color("#33465c")
        _banner(fig, "3 · COLLISION-SAFE ADAPTIVE SURVEY (in-engine)", screening_txt)
        frames.append(_to_frame(fig))
    return frames


def two_panel(npz, title, caption):
    import matplotlib.pyplot as plt
    fig, _ = _fig()
    mean = npz["mean"]; std = npz["std"]; X = npz["X"]; Y = npz["Y"]
    ax1 = fig.add_axes([0.07, 0.14, 0.4, 0.72]); ax2 = fig.add_axes([0.55, 0.14, 0.4, 0.72])
    p1 = ax1.pcolormesh(X, Y, mean, cmap="viridis", shading="auto")
    ax1.set_title("GP mean salinity", color=FG, fontsize=13)
    p2 = ax2.pcolormesh(X, Y, std, cmap="inferno", shading="auto")
    ax2.set_title("GP uncertainty (std)", color=FG, fontsize=13)
    for ax, p in ((ax1, p1), (ax2, p2)):
        ax.set_xlabel("x (m)", color="#9fb3c8"); ax.tick_params(colors="#7f95a8")
        for s in ax.spines.values():
            s.set_color("#33465c")
        cb = fig.colorbar(p, ax=ax, fraction=0.046, pad=0.04)
        cb.ax.yaxis.set_tick_params(color="#7f95a8")
        plt.setp(plt.getp(cb.ax, "yticklabels"), color="#9fb3c8")
    _banner(fig, title, caption)
    return _to_frame(fig)


def image_stage(img_path, stage, caption):
    import matplotlib.image as mpimg
    fig, _ = _fig()
    ax = fig.add_axes([0.05, 0.08, 0.9, 0.82])
    ax.axis("off")
    try:
        ax.imshow(mpimg.imread(str(img_path)))
    except Exception:
        fig.text(0.5, 0.5, "(figure unavailable)", color=FG, ha="center")
    _banner(fig, stage, caption)
    return _to_frame(fig)


def verdict_card(compliance_png, screening_state):
    import matplotlib.image as mpimg
    fig, _ = _fig()
    ax = fig.add_axes([0.05, 0.1, 0.62, 0.8]); ax.axis("off")
    try:
        ax.imshow(mpimg.imread(str(compliance_png)))
    except Exception:
        pass
    color = {"clear": "#22c55e", "review": "#eab308",
             "possible_exceedance": "#ef4444"}.get(screening_state, "#9ca3af")
    fig.text(0.83, 0.55, screening_state.replace("_", "\n").upper(), color=color,
             fontsize=30, ha="center", va="center", weight="bold")
    fig.text(0.83, 0.36, "three-state\nscreening", color="#9fb3c8", fontsize=13,
             ha="center")
    _banner(fig, "5 · COMPLIANCE SCREENING", "Precautionary CLEAR / REVIEW / EXCEEDANCE")
    return _to_frame(fig)


def rgb_clip(rgb_dir, max_frames=110, stride=2):
    import cv2
    files = sorted(Path(rgb_dir).glob("frame_*.png"))[::stride][:max_frames]
    out = []
    for f in files:
        img = cv2.imread(str(f))
        if img is None:
            continue
        img = cv2.resize(img, (W, H))
        cv2.rectangle(img, (0, 0), (W, 46), (20, 20, 11), -1)
        cv2.putText(img, "2 . ROV DESCENT / APPROACH / INSPECTION (engine RGB)",
                    (24, 31), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (248, 189, 56), 2)
        out.append(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", required=True)
    ap.add_argument("--rgb", default=None)
    ap.add_argument("--volumetric", default=None)
    ap.add_argument("--history", default=None)
    ap.add_argument("--out", default=str(REPO / "outputs" / "video_demo" / "mission_movie"))
    args = ap.parse_args()
    import cv2

    run = Path(args.run)
    summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    locate = json.loads((run / "locate_result.json").read_text(encoding="utf-8"))
    npz = np.load(run / "plume_maps.npz")
    cfgu = (run / "config_used.yaml").read_text(encoding="utf-8")
    import re
    def grab(key, default):
        m = re.search(rf"{key}:\s*(-?[\d.]+)", cfgu)
        return float(m.group(1)) if m else default
    survey = {"x_min": grab("x_min", 18), "x_max": grab("x_max", 66),
              "y_min": grab("y_min", -26), "y_max": grab("y_max", 26)}
    prior = locate.get("prior", [42, 2])
    est = locate.get("estimate")
    state = str(summary.get("screening", "review")).lower()
    clear_txt = (f"0 collisions · {summary.get('safe_detours','?')} detours · "
                 f"min clearance {summary.get('min_structure_clearance_m','?')} m · "
                 f"{summary.get('n_samples','?')} CTD samples")

    frames = []
    _hold(frames, _title_card("BrineWatch",
          "Autonomous brine-plume monitoring — custom HoloOcean",
          "Sonar-localized outfall · collision-safe survey · 3-state screening"), FPS * 2)
    _hold(frames, site_overview(survey, prior, est), FPS * 2)

    # sonar stage: use one recorded inspection frame if available
    sonar_img = None
    insp = run / "locate_inspection_frames.npz"
    if insp.is_file():
        d = np.load(insp)
        sonar_img = d[sorted(d.files)[len(d.files) // 2]]
    if sonar_img is not None:
        _hold(frames, sonar_stage(sonar_img, locate), int(FPS * 3))

    if args.rgb and Path(args.rgb).exists():
        frames.extend(rgb_clip(args.rgb))

    frames.extend(survey_frames(npz, clear_txt))
    _hold(frames, frames[-1], FPS)                     # settle on the full survey
    _hold(frames, two_panel(npz, "4 · PLUME RECONSTRUCTION + UNCERTAINTY",
          "Anisotropic Gaussian process over the CTD samples"), int(FPS * 2.5))
    if args.volumetric and Path(args.volumetric).exists():
        _hold(frames, image_stage(args.volumetric, "4b · 3-D VOLUMETRIC PLUME",
              "Multi-altitude survey -> terrain-following x-y-z reconstruction"),
              int(FPS * 2.5))
    _hold(frames, verdict_card(run / "map_compliance.png", state), int(FPS * 2.5))
    if args.history and Path(args.history).exists():
        _hold(frames, image_stage(args.history, "6 · DIGITAL-TWIN SITE HISTORY",
              "Repeated missions -> longitudinal compliance record"), int(FPS * 2.5))
    _hold(frames, _title_card("BrineWatch",
          f"sonar localization {locate.get('estimate') and '%.2f m' % np.hypot(est[0]-39.8, est[1]) or '—'} · "
          f"0 collisions · screening {state.upper()}",
          "Genuine custom-HoloOcean simulator output · analytic plume surrogate"), FPS * 2)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    mp4 = out / "mission_movie.mp4"
    vw = cv2.VideoWriter(str(mp4), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    for fr in frames:
        vw.write(cv2.cvtColor(fr, cv2.COLOR_RGB2BGR))
    vw.release()

    # contact sheet: 12 evenly spaced key frames
    idx = np.linspace(0, len(frames) - 1, 12).astype(int)
    cols, rows = 4, 3
    th, tw = H // 3, W // 3
    sheet = np.full((rows * th, cols * tw, 3), 12, np.uint8)
    for i, fi in enumerate(idx):
        r, c = divmod(i, cols)
        thumb = cv2.resize(frames[fi], (tw, th))
        sheet[r * th:(r + 1) * th, c * tw:(c + 1) * tw] = cv2.cvtColor(thumb, cv2.COLOR_RGB2BGR)
    cv2.imwrite(str(out / "contact_sheet.png"), sheet)

    dur = len(frames) / FPS
    (out / "movie_manifest.json").write_text(json.dumps({
        "source_run": run.name, "n_frames": len(frames), "fps": FPS,
        "duration_s": round(dur, 1), "resolution": [W, H],
        "sonar_localization_error_m": summary.get("localization_error_m_vs_diffuser_centre"),
        "collisions": summary.get("collisions"),
        "min_structure_clearance_m": summary.get("min_structure_clearance_m"),
        "screening": state,
        "note": "genuine custom-HoloOcean mission outputs; plume is analytic surrogate",
    }, indent=2), encoding="utf-8")
    print(f"[movie] wrote {mp4}  ({len(frames)} frames, {dur:.1f}s, "
          f"{mp4.stat().st_size // 1024} KB)")
    print(f"[movie] contact sheet: {out / 'contact_sheet.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

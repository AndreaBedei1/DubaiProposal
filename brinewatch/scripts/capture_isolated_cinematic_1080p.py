"""Capture a genuine continuous Full-HD custom-HoloOcean inspection clip.

Run only through ``run_isolated_custom_session.py``.  The BlueROV2 camera is
teleported along a C2-smoothed cinematic trajectory in the live simulated
scene, producing consecutive engine-rendered frames at 30 fps.  This is a
dedicated cinematic path, not a telemetry-synchronised replay of the science
mission; the accepted outfall geometry is built unchanged.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from brinewatch.simulation.custom_engine import (
    activate_fork_client, attach_custom_environment, discover_custom_engine,
    isolated_instance_id, make_asset_spawner)
from brinewatch.simulation.outfall_scene import OutfallSceneBuilder, OutfallSceneConfig
from brinewatch.utils.config import load_config
from brinewatch.utils.terrain import TerrainMap

AGENT = "cinematic_rov"


def smoothstep5(t):
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def interpolate(keys, frames_per_leg):
    for i in range(len(keys) - 1):
        p0, l0, phase = keys[i]
        p1, l1, _ = keys[i + 1]
        for frame in range(frames_per_leg):
            u = smoothstep5(frame / frames_per_leg)
            pos = np.asarray(p0) * (1.0 - u) + np.asarray(p1) * u
            look = np.asarray(l0) * (1.0 - u) + np.asarray(l1) * u
            yield pos, look, phase
    yield np.asarray(keys[-1][0]), np.asarray(keys[-1][1]), keys[-1][2]


def look_rotation(pos, look):
    delta = np.asarray(look) - np.asarray(pos)
    yaw = math.degrees(math.atan2(delta[1], delta[0]))
    pitch = math.degrees(math.atan2(delta[2], math.hypot(delta[0], delta[1])))
    return [0.0, pitch, yaw]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default=str(
        REPO / "configs" / "pfh2026_flagship_custom.yaml"))
    ap.add_argument("--terrain", required=True)
    ap.add_argument("--out", default=os.environ.get(
        "BRINEWATCH_SESSION_OUTPUT_DIR", str(REPO / "outputs")))
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--seconds-per-leg", type=float, default=2.6)
    args = ap.parse_args()
    if (args.width, args.height) < (1920, 1080):
        raise SystemExit("Full-HD capture requires at least 1920 x 1080")

    cfg = load_config(args.config)
    terrain = TerrainMap.from_npz(args.terrain)
    engine = discover_custom_engine(level=cfg.backend.holoocean.world)
    holoocean = activate_fork_client(engine)
    instance_id = isolated_instance_id()
    W, H = args.width, args.height
    start = [cfg.outfall.x - 20.0, cfg.outfall.y + 18.0,
             float(terrain.z(cfg.outfall.x - 20.0,
                             cfg.outfall.y + 18.0)) + 10.0]
    scenario = {
        "name": "brinewatch_cinematic_1080p",
        "package_name": cfg.backend.holoocean.package_name,
        "world": engine.level,
        "main_agent": AGENT,
        "ticks_per_sec": args.fps,
        "frames_per_sec": args.fps,
        "agents": [{
            "agent_name": AGENT,
            "agent_type": "BlueROV2",
            "sensors": [
                {"sensor_type": "LocationSensor", "socket": "IMUSocket"},
                {"sensor_type": "PoseSensor", "socket": "IMUSocket"},
                {"sensor_type": "RGBCamera", "socket": "CameraSocket",
                 "configuration": {"CaptureWidth": W, "CaptureHeight": H}},
            ],
            "control_scheme": 1,
            "location": start,
            "rotation": [0.0, 0.0, 0.0],
        }],
        "window_width": W,
        "window_height": H,
    }
    env = attach_custom_environment(
        holoocean, scenario, show_viewport=True, verbose=False,
        instance_id=instance_id)
    agent = env.agents[AGENT]
    out = Path(args.out) / "cinematic_1080p"
    key_dir = out / "keyframes"
    key_dir.mkdir(parents=True, exist_ok=True)
    try:
        builder = OutfallSceneBuilder(
            env=env, agent_name=AGENT, outfall=cfg.outfall,
            scene=OutfallSceneConfig(), terrain=terrain,
            spawn_fn=make_asset_spawner(env, holoocean,
                                        label_prefix="brinewatch_cinematic"))
        built = builder.build()
        builder.save_manifest(out / "scene_manifest.json")
        for _ in range(45):
            env.tick()
        if sum(component.ok for component in built) != len(built):
            raise RuntimeError("not every accepted outfall component was spawned")

        def w(s, t, h):
            x, y = builder.to_world(s, t)
            return [x, y, builder.bed(s, t) + h]

        L = builder.scene.diffuser_length_m
        keys = [
            (w(-22, 18, 10), w(2, 0, 1.2), "site_and_descent"),
            (w(-16, 12, 6), w(0, 0, 1.1), "early_acquisition"),
            (w(-12, 7, 3.8), w(4, 0, 1.1), "pipeline_approach"),
            (w(-4, 5.2, 2.8), w(10, 0, 1.3), "follow_pipeline"),
            (w(5, 4.6, 2.5), w(11, 0, 1.5), "riser_inspection"),
            (w(13, 4.0, 2.4), w(15, 0, 1.6), "lateral_pass"),
            (w(L + 1, 3.0, 2.2), w(L - 4, 0, 1.5), "close_nozzles"),
            (w(L + 4, -6.5, 3.3), w(L / 2, 0, 1.3), "cross_over"),
            (w(L / 2, -13, 6.5), w(L / 2, 0, 1.2), "wide_reveal"),
        ]
        frames_per_leg = max(2, int(round(args.seconds_per_leg * args.fps)))
        path = list(interpolate(keys, frames_per_leg))
        mp4 = out / "BrineWatch_HoloOcean_Continuous_1080p_Source.mp4"
        writer = cv2.VideoWriter(str(mp4), cv2.VideoWriter_fourcc(*"mp4v"),
                                 args.fps, (W, H))
        if not writer.isOpened():
            raise RuntimeError("OpenCV could not open the Full-HD MP4 writer")
        log = []
        last_bgr = None
        black_frames = 0
        phases_saved = set()
        for idx, (pos, look, phase) in enumerate(path):
            rotation = look_rotation(pos, look)
            agent.teleport(pos.tolist(), rotation)
            state = env.tick()
            raw = np.asarray(state.get("RGBCamera"))
            if raw.ndim != 3 or raw.shape[0] != H or raw.shape[1] != W:
                raise RuntimeError(f"unexpected camera frame shape {raw.shape}")
            bgr = np.ascontiguousarray(raw[:, :, :3])
            pixel_mean = float(bgr.mean())
            if pixel_mean < 2.0:
                black_frames += 1
            motion = (float(np.mean(cv2.absdiff(bgr, last_bgr)))
                      if last_bgr is not None else 0.0)
            writer.write(bgr)
            if phase not in phases_saved or idx in (0, len(path) - 1):
                cv2.imwrite(str(key_dir / f"{idx:04d}_{phase}.png"), bgr)
                phases_saved.add(phase)
            log.append({
                "frame": idx, "phase": phase,
                "position": [round(float(v), 4) for v in pos],
                "look_at": [round(float(v), 4) for v in look],
                "rotation_rpy_deg": [round(float(v), 4) for v in rotation],
                "pixel_mean": round(pixel_mean, 3),
                "mean_abs_frame_delta": round(motion, 3),
            })
            last_bgr = bgr
            if idx % args.fps == 0:
                print(f"[cinematic-1080p] {idx}/{len(path)} {phase} "
                      f"mean={pixel_mean:.1f} motion={motion:.2f}")
        writer.release()
        if black_frames:
            raise RuntimeError(f"captured {black_frames} black Full-HD frame(s)")
        (out / "camera_pose_log.json").write_text(
            json.dumps(log, indent=2), encoding="utf-8")

        images = sorted(key_dir.glob("*.png"))
        thumbs = [cv2.imread(str(path)) for path in images]
        thumb_w, thumb_h = 480, 270
        sheet = np.full((thumb_h * 3, thumb_w * 3, 3), 8, dtype=np.uint8)
        for i, image in enumerate(thumbs[:9]):
            y, x = divmod(i, 3)
            sheet[y * thumb_h:(y + 1) * thumb_h,
                  x * thumb_w:(x + 1) * thumb_w] = cv2.resize(
                      image, (thumb_w, thumb_h), interpolation=cv2.INTER_AREA)
        cv2.imwrite(str(out / "cinematic_contact_sheet.png"), sheet)
        manifest = {
            "file": str(mp4.resolve()),
            "type": "genuine continuous custom-HoloOcean RGB capture",
            "resolution": [W, H], "fps": args.fps,
            "frames": len(path), "duration_s": len(path) / args.fps,
            "black_frames": black_frames,
            "continuous_motion_evidence": {
                "mean_frame_delta": round(float(np.mean([
                    row["mean_abs_frame_delta"] for row in log[1:]])), 3),
                "moving_frame_fraction": round(float(np.mean([
                    row["mean_abs_frame_delta"] > 0.2 for row in log[1:]])), 3),
            },
            "accepted_geometry_changed": False,
            "cinematic_disclosure": ("dedicated smooth simulated camera path; "
                                     "not telemetry-synchronised science replay"),
            "rendering": ("native engine underwater rendering; no Ken Burns, "
                          "static-image animation or flat haze filter"),
            "instance_id": instance_id,
        }
        (out / "video_manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8")
        print(f"[cinematic-1080p] DONE -> {mp4}")
    finally:
        exit_fn = getattr(env, "__on_exit__", None)
        if callable(exit_fn):
            exit_fn()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

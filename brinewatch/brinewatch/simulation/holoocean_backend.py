"""HoloOcean backend: drives the native BlueROV2 agent in HoloOcean 2.x.

Verified against the installed HoloOcean 2.3.0 (see docs/holoocean_notes.md):

- Custom scenario dicts require ``package_name``; we build one programmatically
  with a BlueROV2 agent and PoseSensor / LocationSensor / VelocitySensor /
  DepthSensor / DVLSensor / RangeFinderSensor.
- BlueROV2 ``control_scheme=1`` is the built-in PID controller taking
  ``[des_x, des_y, des_z, roll, pitch, yaw]`` (yaw in degrees). Verified
  empirically: commanded [5, 5, -12] converges to within ~0.15 m.
- ``frames_per_sec=False`` uncaps the simulation (~2.5x real time here).
- ``env.spawn_prop`` exists and is used to build a visible outfall pipe +
  diffuser risers on the seabed (visual/acoustic decoration; the plume field
  and the locator detection model remain analytic).
- Altitude is measured with a down-looking RangeFinderSensor.
"""
from __future__ import annotations

import math
from typing import Optional, Tuple

import numpy as np

from ..utils.config import BackendConfig, EnvironmentConfig, OutfallConfig
from ..utils.types import VehicleState, Waypoint
from .base import SimulatorBackend

AGENT_NAME = "brine_rov"


def build_scenario(cfg: BackendConfig, start_position: Tuple[float, float, float]) -> dict:
    ho = cfg.holoocean
    return {
        "name": "brinewatch",
        "package_name": ho.package_name,
        "world": ho.world,
        "main_agent": AGENT_NAME,
        "ticks_per_sec": ho.ticks_per_sec,
        "frames_per_sec": ho.frames_per_sec,
        "agents": [
            {
                "agent_name": AGENT_NAME,
                "agent_type": "BlueROV2",
                "sensors": [
                    {"sensor_type": "PoseSensor", "socket": "IMUSocket"},
                    {"sensor_type": "LocationSensor", "socket": "IMUSocket"},
                    {"sensor_type": "VelocitySensor", "socket": "IMUSocket"},
                    {"sensor_type": "DepthSensor", "socket": "DepthSocket",
                     "configuration": {"Sigma": 0.05}},
                    {"sensor_type": "DVLSensor", "socket": "DVLSocket",
                     "configuration": {"ReturnRange": True, "MaxRange": 60}},
                    {"sensor_type": "RangeFinderSensor", "socket": "SonarSocket",
                     "configuration": {"LaserCount": 4, "LaserAngle": -90,
                                       "LaserMaxDistance": 50}},
                    {"sensor_type": "CollisionSensor", "socket": "COM"},
                ],
                "control_scheme": 1,  # PID: [x, y, z, roll, pitch, yaw(deg)]
                "location": list(start_position),
                "rotation": [0.0, 0.0, 0.0],
            }
        ],
        "window_width": ho.window_width,
        "window_height": ho.window_height,
    }


class HoloOceanBackend(SimulatorBackend):
    def __init__(
        self,
        cfg: BackendConfig,
        env_cfg: EnvironmentConfig,
        outfall_cfg: OutfallConfig,
        start_position: Tuple[float, float, float],
        seed: int = 0,
    ):
        import holoocean  # lazy: only needed for this backend

        self.cfg = cfg
        self.ho = cfg.holoocean
        self.env_cfg = env_cfg
        self.outfall_cfg = outfall_cfg
        self._start = tuple(float(v) for v in start_position)
        self._scenario = build_scenario(cfg, self._start)
        self._env = holoocean.make(
            scenario_cfg=self._scenario,
            show_viewport=self.ho.show_viewport,
            verbose=False,
        )
        self._t = 0.0
        self._yaw_cmd_deg = 0.0
        self._last_state: Optional[VehicleState] = None
        if self.ho.spawn_outfall_props:
            self._spawn_outfall_props()

    # ------------------------------------------------------------------ #
    @property
    def name(self) -> str:
        return "holoocean"

    @property
    def control_period_s(self) -> float:
        return self.ho.control_ticks / float(self.ho.ticks_per_sec)

    def reset(self) -> VehicleState:
        # Note: env.reset() would also despawn props, so we only reset once at
        # construction; subsequent reset() re-reads the state.
        state = self._tick_n(1, self._hold_command())
        self._last_state = state
        return state

    def step_toward(self, waypoint: Waypoint) -> VehicleState:
        prev = self._last_state
        # Point the nose along the direction of travel (helps sensor realism)
        if prev is not None:
            dx, dy = waypoint.x - prev.x, waypoint.y - prev.y
            if math.hypot(dx, dy) > 1.5:
                self._yaw_cmd_deg = math.degrees(math.atan2(dy, dx))

        # Depth command: waypoint z encodes an intended altitude above the
        # *analytic* seabed plane; the real terrain differs from that plane,
        # so re-reference the command to the measured altitude (terrain
        # following) instead of trusting the absolute z. Without an altitude
        # reading fall back to the analytic floor.
        z_cmd = waypoint.z
        if prev is not None:
            if prev.altitude is not None:
                desired_alt = max(
                    self.ho.min_altitude_m,
                    waypoint.z - self._analytic_bed(waypoint.x, waypoint.y),
                )
                real_bed_here = prev.z - prev.altitude
                z_cmd = real_bed_here + desired_alt
            else:
                z_cmd = max(
                    z_cmd,
                    self._analytic_bed(prev.x, prev.y) + self.ho.min_altitude_m,
                )
            # Reactive escape: on contact (steep terrain outrunning the
            # 0.5 s terrain-following update) pop up above the obstacle.
            if prev.collided:
                z_cmd = max(z_cmd, prev.z + 3.0)
        cmd = np.array([waypoint.x, waypoint.y, z_cmd, 0.0, 0.0, self._yaw_cmd_deg],
                       dtype=np.float64)
        state = self._tick_n(self.ho.control_ticks, cmd)
        self._last_state = state
        return state

    def _analytic_bed(self, x: float, y: float) -> float:
        env = self.env_cfg
        return env.seabed_z0 + env.seabed_slope_x * x + env.seabed_slope_y * y

    def close(self) -> None:
        exit_fn = getattr(self._env, "__on_exit__", None)
        if callable(exit_fn):
            try:
                exit_fn()
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    def draw_waypoint(self, wp: Waypoint) -> None:
        if self.ho.draw_debug:
            try:
                self._env.draw_point([wp.x, wp.y, wp.z], color=[0, 255, 0], lifetime=30)
            except Exception:
                pass

    def _hold_command(self) -> np.ndarray:
        s = self._start
        return np.array([s[0], s[1], s[2], 0.0, 0.0, 0.0], dtype=np.float64)

    def _tick_n(self, n: int, cmd: np.ndarray) -> VehicleState:
        state_dict = None
        for _ in range(max(1, n)):
            self._env.act(AGENT_NAME, cmd)
            state_dict = self._env.tick()
        return self._parse_state(state_dict)

    def _parse_state(self, sd: dict) -> VehicleState:
        loc = np.asarray(sd["LocationSensor"], dtype=float)
        vel = np.asarray(sd.get("VelocitySensor", np.zeros(3)), dtype=float)
        pose = np.asarray(sd.get("PoseSensor", np.eye(4)), dtype=float)
        yaw = math.atan2(pose[1, 0], pose[0, 0])
        roll = math.atan2(pose[2, 1], pose[2, 2])
        pitch = -math.asin(max(-1.0, min(1.0, pose[2, 0])))
        self._t = float(sd.get("t", self._t + 1.0 / self.ho.ticks_per_sec))

        altitude: Optional[float] = None
        rf = sd.get("RangeFinderSensor")
        if rf is not None:
            ranges = np.asarray(rf, dtype=float)
            valid = ranges[ranges > 0]
            if valid.size:
                altitude = float(valid.min())

        cs = sd.get("CollisionSensor")
        collided = bool(np.any(np.asarray(cs))) if cs is not None else False

        return VehicleState(
            t=self._t,
            x=float(loc[0]), y=float(loc[1]), z=float(loc[2]),
            roll=roll, pitch=pitch, yaw=yaw,
            vx=float(vel[0]), vy=float(vel[1]), vz=float(vel[2]),
            altitude=altitude,
            collided=collided,
        )

    # ------------------------------------------------------------------ #
    def _spawn_outfall_props(self) -> None:
        """Build a visible outfall: pipe segments leading to a diffuser with
        risers. Props are static (sim_physics=False) and placed relative to the
        *analytic* seabed plane; small mismatches with the real terrain are
        cosmetic (documented approximation)."""
        env_cfg = self.env_cfg
        out = self.outfall_cfg
        bed = self._analytic_bed

        theta_c = math.radians(env_cfg.current_dir_deg)
        e_up = (-math.cos(theta_c), -math.sin(theta_c))  # upstream, toward "shore"
        pipe_yaw_deg = math.degrees(math.atan2(e_up[1], e_up[0]))

        try:
            # Pipe: segments from the outfall heading upstream out of the box
            seg_len, n_seg = 4.0, 8
            for i in range(n_seg):
                d = (i + 0.5) * seg_len
                x = out.x + e_up[0] * d
                y = out.y + e_up[1] * d
                self._env.spawn_prop(
                    "cylinder",
                    location=[x, y, bed(x, y) + 0.4],
                    rotation=[0.0, 90.0, pipe_yaw_deg],
                    scale=[0.6, 0.6, seg_len],
                    sim_physics=False,
                    material="steel",
                )
            # Diffuser manifold
            self._env.spawn_prop(
                "box",
                location=[out.x, out.y, bed(out.x, out.y) + 0.5],
                rotation=[0.0, 0.0, out.axis_deg],
                scale=[out.port_spacing_m * out.n_ports, 1.0, 1.0],
                sim_physics=False,
                material="steel",
            )
            # Risers along the diffuser axis
            ax = math.radians(out.axis_deg)
            for k in range(out.n_ports):
                off = (k - (out.n_ports - 1) / 2.0) * out.port_spacing_m
                x = out.x + math.cos(ax) * off
                y = out.y + math.sin(ax) * off
                self._env.spawn_prop(
                    "cylinder",
                    location=[x, y, bed(x, y) + out.riser_height_m / 2.0 + 0.4],
                    rotation=[0.0, 0.0, 0.0],
                    scale=[0.3, 0.3, out.riser_height_m],
                    sim_physics=False,
                    material="steel",
                )
        except Exception as exc:  # pragma: no cover - engine-dependent
            # Props are decoration: a failure must never kill a mission.
            print(f"[holoocean_backend] spawn_prop failed (continuing): {exc}")

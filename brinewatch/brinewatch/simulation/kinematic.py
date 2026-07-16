"""Fast kinematic backend: no rendering, no external dependencies.

First-order velocity dynamics with separate horizontal/vertical speed limits:
realistic enough to make travel distance and time meaningful, and fast enough
to run benchmarks over many seeds in seconds. Reported positions can carry
Gaussian noise to emulate a navigation solution.
"""
from __future__ import annotations

import math
from typing import Callable, Tuple

import numpy as np

from ..utils.config import BackendConfig, EnvironmentConfig
from ..utils.types import VehicleState, Waypoint
from .base import SimulatorBackend


class KinematicBackend(SimulatorBackend):
    def __init__(
        self,
        cfg: BackendConfig,
        env_cfg: EnvironmentConfig,
        start_position: Tuple[float, float, float],
        seed: int = 0,
    ):
        self.cfg = cfg
        self.kin = cfg.kinematic
        self._dt = cfg.dt_control_s
        self._seabed_fn: Callable = lambda x, y: (
            env_cfg.seabed_z0 + env_cfg.seabed_slope_x * x + env_cfg.seabed_slope_y * y
        )
        self._start = np.asarray(start_position, dtype=float)
        self._rng = np.random.default_rng(seed)
        self._pos = self._start.copy()
        self._vel = np.zeros(3)
        self._t = 0.0
        self._yaw = 0.0

    # ------------------------------------------------------------------ #
    @property
    def name(self) -> str:
        return "kinematic"

    @property
    def control_period_s(self) -> float:
        return self._dt

    def reset(self) -> VehicleState:
        self._pos = self._start.copy()
        self._vel = np.zeros(3)
        self._t = 0.0
        self._yaw = 0.0
        return self._state()

    def step_toward(self, waypoint: Waypoint) -> VehicleState:
        delta = waypoint.position - self._pos
        dist_h = math.hypot(delta[0], delta[1])
        dist_v = abs(delta[2])

        # Desired velocity: full speed toward the target, slowing near arrival
        v_des = np.zeros(3)
        if dist_h > 1e-6:
            speed_h = min(self.kin.max_speed_h_mps, dist_h / self._dt)
            v_des[:2] = delta[:2] / dist_h * speed_h
        if dist_v > 1e-6:
            speed_v = min(self.kin.max_speed_v_mps, dist_v / self._dt)
            v_des[2] = math.copysign(speed_v, delta[2])

        # First-order response toward the desired velocity
        blend = 1.0 - math.exp(-self._dt / max(1e-6, self.kin.accel_tau_s))
        self._vel = self._vel + (v_des - self._vel) * blend
        self._pos = self._pos + self._vel * self._dt
        self._t += self._dt
        if np.hypot(self._vel[0], self._vel[1]) > 0.05:
            self._yaw = math.atan2(self._vel[1], self._vel[0])
        return self._state()

    # ------------------------------------------------------------------ #
    def _state(self) -> VehicleState:
        noise = self._rng.normal(0.0, self.kin.position_noise_sigma_m, size=3) \
            if self.kin.position_noise_sigma_m > 0 else np.zeros(3)
        reported = self._pos + noise
        bed = float(self._seabed_fn(self._pos[0], self._pos[1]))
        return VehicleState(
            t=self._t,
            x=float(reported[0]),
            y=float(reported[1]),
            z=float(reported[2]),
            yaw=self._yaw,
            vx=float(self._vel[0]),
            vy=float(self._vel[1]),
            vz=float(self._vel[2]),
            altitude=float(self._pos[2] - bed),
        )

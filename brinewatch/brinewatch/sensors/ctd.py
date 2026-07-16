"""Virtual CT(D) payload: samples the analytic plume at the vehicle pose.

This emulates a small conductivity-temperature probe (plus the vehicle's
pressure sensor) mounted on the ROV: at a fixed rate it reads the *true*
field at the vehicle's position and adds independent Gaussian sensor noise.
Position error comes from the backend's reported pose, exactly like a real
payload georeferenced by the vehicle's navigation solution.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from ..plume.model import BrinePlume
from ..utils.config import CTDConfig
from ..utils.types import CTDSample, VehicleState


class VirtualCTD:
    def __init__(self, cfg: CTDConfig, plume: BrinePlume, seed: int = 0):
        self.cfg = cfg
        self.plume = plume
        self._rng = np.random.default_rng(seed)
        self._period = 1.0 / cfg.rate_hz if cfg.rate_hz > 0 else float("inf")
        self._last_t = -np.inf

    def maybe_sample(self, state: VehicleState) -> Optional[CTDSample]:
        """Return a sample if at least one sampling period elapsed since the last."""
        if state.t - self._last_t < self._period:
            return None
        self._last_t = state.t
        return self.sample(state)

    def sample(self, state: VehicleState) -> CTDSample:
        s_true = float(self.plume.salinity(state.x, state.y, state.z, state.t))
        t_true = float(self.plume.temperature(state.x, state.y, state.z, state.t))
        depth_true = max(0.0, -state.z)
        return CTDSample(
            t=state.t,
            x=state.x,
            y=state.y,
            z=state.z,
            salinity_psu=s_true + self._rng.normal(0.0, self.cfg.salinity_sigma_psu),
            temperature_c=t_true + self._rng.normal(0.0, self.cfg.temperature_sigma_c),
            depth_m=depth_true + self._rng.normal(0.0, self.cfg.depth_sigma_m),
        )

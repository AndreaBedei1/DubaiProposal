"""Analytic brine plume model.

IMPORTANT — honesty note (see docs/assumptions.md):
This is a *synthetic, analytic surrogate* of a negatively-buoyant brine
discharge, inspired by the phenomenology of dense-jet/gravity-current
literature (Roberts et al.): the dense jet rises a few metres above the
diffuser ports, collapses onto the seabed a few metres downstream, and then
spreads as a bottom-hugging gravity current that widens and dilutes with
distance while being advected by the ambient current and tide. It is NOT a
CFD solution and must not be used as physical ground truth for real sites.
Its role here is to provide a controllable, differentiable, seeded field with
realistic *structure* so that sampling strategies and reconstruction can be
compared quantitatively (we know the exact ground truth by construction).
"""
from __future__ import annotations

import math
from typing import Tuple, Union

import numpy as np

from ..utils.config import EnvironmentConfig, OutfallConfig, PlumeConfig

ArrayLike = Union[float, np.ndarray]


class BrinePlume:
    """Salinity/temperature field: ambient water column + brine anomaly."""

    def __init__(self, env: EnvironmentConfig, outfall: OutfallConfig, plume: PlumeConfig):
        self.env = env
        self.outfall = outfall
        self.plume = plume

        theta_c = math.radians(env.current_dir_deg)
        self._e_current = np.array([math.cos(theta_c), math.sin(theta_c)])
        self._e_cross = np.array([-math.sin(theta_c), math.cos(theta_c)])

        theta_a = math.radians(outfall.axis_deg)
        e_axis = np.array([math.cos(theta_a), math.sin(theta_a)])
        offsets = (np.arange(outfall.n_ports) - (outfall.n_ports - 1) / 2.0) * outfall.port_spacing_m
        self._ports_xy = np.array([outfall.x, outfall.y])[None, :] + offsets[:, None] * e_axis[None, :]

        # Far-field source: centroid of port impact points, nearfield_offset downstream.
        self._impact_xy = np.array([outfall.x, outfall.y]) + plume.nearfield_offset_m * self._e_current

    # ------------------------------------------------------------------ #
    # Ambient environment
    # ------------------------------------------------------------------ #
    def seabed_z(self, x: ArrayLike, y: ArrayLike) -> np.ndarray:
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        return self.env.seabed_z0 + self.env.seabed_slope_x * x + self.env.seabed_slope_y * y

    def ambient_salinity(self, z: ArrayLike) -> np.ndarray:
        depth = np.maximum(0.0, -np.asarray(z, dtype=float))
        return self.env.ambient_salinity_psu + self.env.salinity_stratification_per_m * depth

    def ambient_temperature(self, z: ArrayLike) -> np.ndarray:
        depth = np.maximum(0.0, -np.asarray(z, dtype=float))
        return self.env.ambient_temperature_c + self.env.temperature_gradient_per_m * depth

    # ------------------------------------------------------------------ #
    # Anomaly field
    # ------------------------------------------------------------------ #
    def tide_shift_m(self, t: ArrayLike) -> np.ndarray:
        """Horizontal displacement of the plume along the current axis at time t."""
        t = np.asarray(t, dtype=float)
        return self.env.tide_amplitude_m * np.sin(2.0 * math.pi * t / self.env.tide_period_s)

    def salinity_anomaly(self, x: ArrayLike, y: ArrayLike, z: ArrayLike, t: ArrayLike = 0.0) -> np.ndarray:
        """Salinity anomaly (PSU above ambient) at world position(s) and time."""
        x, y, z, t = np.broadcast_arrays(
            np.asarray(x, dtype=float), np.asarray(y, dtype=float),
            np.asarray(z, dtype=float), np.asarray(t, dtype=float),
        )
        p = self.plume

        # The tide advects the whole anomaly pattern along the current axis:
        # evaluate the static pattern at the tide-corrected position.
        shift = self.tide_shift_m(t)
        qx = x - shift * self._e_current[0]
        qy = y - shift * self._e_current[1]

        bed = self.seabed_z(qx, qy)
        h_above_bed = np.maximum(0.0, z - bed)

        # --- Near field: one collapsing-jet blob per diffuser port ------- #
        near = np.zeros_like(qx)
        blob_dx = 0.5 * p.nearfield_offset_m * self._e_current[0]
        blob_dy = 0.5 * p.nearfield_offset_m * self._e_current[1]
        for px, py in self._ports_xy:
            cx, cy = px + blob_dx, py + blob_dy
            cz = self.seabed_z(cx, cy) + self.outfall.riser_height_m + p.rise_height_m
            d_xy2 = ((qx - cx) ** 2 + (qy - cy) ** 2) / (p.nearfield_sigma_xy_m ** 2)
            d_z2 = ((z - cz) ** 2) / (p.nearfield_sigma_z_m ** 2)
            near = near + p.nearfield_peak_anomaly_psu * np.exp(-0.5 * (d_xy2 + d_z2))

        # --- Far field: bottom gravity current --------------------------- #
        rel_x = qx - self._impact_xy[0]
        rel_y = qy - self._impact_xy[1]
        r_down = rel_x * self._e_current[0] + rel_y * self._e_current[1]
        s_cross = rel_x * self._e_cross[0] + rel_y * self._e_cross[1]

        amp_down = np.where(
            r_down >= 0.0,
            1.0 / (1.0 + r_down / p.dilution_length_m),
            np.exp(r_down / p.upstream_tail_m),
        )
        width = p.farfield_initial_width_m + p.farfield_spread_rate * np.maximum(r_down, 0.0)
        cross = np.exp(-0.5 * (s_cross / width) ** 2)
        vert = np.exp(-h_above_bed / p.layer_thickness_m)
        far = p.farfield_peak_anomaly_psu * amp_down * cross * vert

        anomaly = near + far
        max_anomaly = self.outfall.discharge_salinity_psu - self.ambient_salinity(z)
        return np.minimum(anomaly, np.maximum(max_anomaly, 0.0))

    # ------------------------------------------------------------------ #
    # Public fields
    # ------------------------------------------------------------------ #
    def salinity(self, x: ArrayLike, y: ArrayLike, z: ArrayLike, t: ArrayLike = 0.0) -> np.ndarray:
        return self.ambient_salinity(z) + self.salinity_anomaly(x, y, z, t)

    def temperature(self, x: ArrayLike, y: ArrayLike, z: ArrayLike, t: ArrayLike = 0.0) -> np.ndarray:
        return (self.ambient_temperature(z)
                + self.plume.temperature_anomaly_ratio * self.salinity_anomaly(x, y, z, t))

    def outfall_xy(self) -> Tuple[float, float]:
        return (self.outfall.x, self.outfall.y)

    def ground_truth(self, points: np.ndarray, t: float = 0.0) -> np.ndarray:
        """Salinity at an (N, 3) array of points at time t."""
        pts = np.asarray(points, dtype=float)
        return self.salinity(pts[:, 0], pts[:, 1], pts[:, 2], t)

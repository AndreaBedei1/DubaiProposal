"""Config-driven outfall scene builder for official HoloOcean.

Builds a visually credible desalination outfall — incoming seabed pipe,
diffuser manifold, risers with nozzle heads and base collars — using ONLY
official ``spawn_prop`` primitives, placed on the *measured* seabed:

1. (optional) an automated calibration pass teleports the vehicle over a
   small grid around the outfall and sounds the bottom with the down-looking
   RangeFinder (official sensors only), producing a local
   :class:`~brinewatch.utils.terrain.TerrainMap`;
2. every component's z (and each pipe segment's pitch) comes from that map,
   so nothing floats or sinks where the real terrain deviates from a plane;
3. the final geometry is logged and saved as a JSON manifest.

HONESTY NOTE (verified in outputs/sonar_visibility_*): spawned props are
visual and collidable but NOT part of HoloOcean's acoustic octree. The
acoustic localization target of the official mission is therefore stock
world geometry (see docs/application/pfh2026/SONAR_VALIDATION.md); this
scene provides the visual/collision layer co-located with it.

Mission-critical components (manifold, risers) raise
:class:`SceneBuildError` on failure; cosmetic ones (pipe, nozzles, collars)
log a warning and continue.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Union

import numpy as np

from ..utils.config import OutfallConfig
from ..utils.terrain import TerrainMap


class SceneBuildError(RuntimeError):
    """A mission-critical scene component could not be spawned."""


@dataclass
class OutfallSceneConfig:
    """Visual geometry parameters (dimensions in metres)."""

    pipe_length_m: float = 36.0
    pipe_segment_m: float = 6.0
    pipe_diameter_m: float = 0.9
    manifold_height_m: float = 1.1
    manifold_width_m: float = 1.2
    riser_height_m: float = 1.6
    riser_diameter_m: float = 0.45
    nozzle_height_m: float = 0.5
    collar_diameter_m: float = 1.4
    collar_height_m: float = 0.25
    material: str = "steel"
    with_nozzles: bool = True
    with_collars: bool = True
    # Calibration probe grid (around the outfall), used when a live env probe
    # is requested: extent (half-size) and spacing of the sounding pattern.
    probe_half_extent_m: float = 24.0
    probe_spacing_m: float = 6.0
    probe_hold_z_m: float = 8.0  # probe altitude above the deepest expected bed


@dataclass
class SpawnedComponent:
    kind: str
    prop_type: str
    location: List[float]
    rotation: List[float]
    scale: List[float]
    critical: bool
    ok: bool
    error: str = ""


class OutfallSceneBuilder:
    """Builds the outfall scene in a live HoloOcean environment."""

    def __init__(
        self,
        env,
        agent_name: str,
        outfall: OutfallConfig,
        scene: OutfallSceneConfig = OutfallSceneConfig(),
        terrain: Optional[TerrainMap] = None,
        upstream_dir_rad: float = math.pi,  # direction the pipe runs AWAY from the diffuser
        log: Callable[[str], None] = print,
    ):
        self.env = env
        self.agent_name = agent_name
        self.outfall = outfall
        self.scene = scene
        self.terrain = terrain
        self.upstream_dir = upstream_dir_rad
        self.log = log
        self.components: List[SpawnedComponent] = []

    # ------------------------------------------------------------------ #
    # Terrain calibration (official sensors only)
    # ------------------------------------------------------------------ #
    def probe_terrain(self, reference_bed_z: float) -> TerrainMap:
        """Automated calibration pass: sound the bottom on a grid around the
        outfall with the vehicle's down-looking RangeFinder (via teleport)."""
        sc = self.scene
        cx, cy = self.outfall.x, self.outfall.y
        xs = np.arange(cx - sc.probe_half_extent_m, cx + sc.probe_half_extent_m + 1e-6,
                       sc.probe_spacing_m)
        ys = np.arange(cy - sc.probe_half_extent_m, cy + sc.probe_half_extent_m + 1e-6,
                       sc.probe_spacing_m)
        hold_z = reference_bed_z + sc.probe_hold_z_m
        agent = self.env.agents[self.agent_name]
        bed = np.full((len(ys), len(xs)), np.nan)
        for i, y in enumerate(ys):
            for j, x in enumerate(xs):
                cmd = np.array([x, y, hold_z, 0.0, 0.0, 0.0], dtype=np.float64)
                agent.teleport([float(x), float(y), hold_z], [0.0, 0.0, 0.0])
                state = None
                for _ in range(10):
                    self.env.act(self.agent_name, cmd)
                    state = self.env.tick()
                rf = np.asarray(state["RangeFinderSensor"], dtype=float)
                valid = rf[rf > 0]
                if valid.size:
                    z = float(np.asarray(state["LocationSensor"], dtype=float)[2])
                    bed[i, j] = z - float(valid.min())
        self.terrain = TerrainMap(xs, ys, bed)
        self.log(f"[outfall_scene] terrain probe: bed z in "
                 f"[{np.nanmin(bed):.2f}, {np.nanmax(bed):.2f}] over "
                 f"{len(xs)}x{len(ys)} soundings")
        return self.terrain

    def _bed(self, x: float, y: float) -> float:
        if self.terrain is None:
            raise SceneBuildError("no terrain model: call probe_terrain() or pass one")
        return float(self.terrain.z(x, y))

    # ------------------------------------------------------------------ #
    # Building
    # ------------------------------------------------------------------ #
    def build(self) -> List[SpawnedComponent]:
        out, sc = self.outfall, self.scene
        ax = math.radians(out.axis_deg)
        e_axis = (math.cos(ax), math.sin(ax))
        e_up = (math.cos(self.upstream_dir), math.sin(self.upstream_dir))

        # --- incoming pipe: segments pitched to the local slope (cosmetic) --- #
        n_seg = max(1, int(round(sc.pipe_length_m / sc.pipe_segment_m)))
        for k in range(n_seg):
            d0 = k * sc.pipe_segment_m
            d1 = d0 + sc.pipe_segment_m
            p0 = (out.x + e_up[0] * d0, out.y + e_up[1] * d0)
            p1 = (out.x + e_up[0] * d1, out.y + e_up[1] * d1)
            mid = ((p0[0] + p1[0]) / 2.0, (p0[1] + p1[1]) / 2.0)
            bed_mid = self._bed(*mid)
            pitch = math.degrees(self.terrain.slope_between(p0, p1))
            yaw = math.degrees(math.atan2(e_up[1], e_up[0]))
            self._spawn(
                kind=f"pipe_segment_{k}", prop_type="cylinder", critical=False,
                location=[mid[0], mid[1], bed_mid + sc.pipe_diameter_m / 2.0],
                # cylinder axis is z; pitch 90 lays it along the yaw direction,
                # then the terrain slope is added so it hugs the bottom.
                rotation=[0.0, 90.0 + pitch, yaw],
                scale=[sc.pipe_diameter_m, sc.pipe_diameter_m, sc.pipe_segment_m],
            )

        # --- diffuser manifold (critical) ---------------------------------- #
        bed_c = self._bed(out.x, out.y)
        manifold_len = out.port_spacing_m * (out.n_ports + 0.5)
        self._spawn(
            kind="manifold", prop_type="box", critical=True,
            location=[out.x, out.y, bed_c + sc.manifold_height_m / 2.0],
            rotation=[0.0, 0.0, out.axis_deg],
            scale=[manifold_len, sc.manifold_width_m, sc.manifold_height_m],
        )

        # --- risers + nozzles + collars ------------------------------------ #
        for k in range(out.n_ports):
            off = (k - (out.n_ports - 1) / 2.0) * out.port_spacing_m
            x = out.x + e_axis[0] * off
            y = out.y + e_axis[1] * off
            bed = self._bed(x, y)
            self._spawn(
                kind=f"riser_{k}", prop_type="cylinder", critical=True,
                location=[x, y, bed + sc.manifold_height_m + sc.riser_height_m / 2.0],
                rotation=[0.0, 0.0, 0.0],
                scale=[sc.riser_diameter_m, sc.riser_diameter_m, sc.riser_height_m],
            )
            if sc.with_nozzles:
                self._spawn(
                    kind=f"nozzle_{k}", prop_type="cone", critical=False,
                    location=[x, y, bed + sc.manifold_height_m + sc.riser_height_m
                              + sc.nozzle_height_m / 2.0],
                    rotation=[0.0, 0.0, 0.0],
                    scale=[sc.riser_diameter_m * 1.6, sc.riser_diameter_m * 1.6,
                           sc.nozzle_height_m],
                )
            if sc.with_collars:
                self._spawn(
                    kind=f"collar_{k}", prop_type="cylinder", critical=False,
                    location=[x, y, bed + sc.collar_height_m / 2.0],
                    rotation=[0.0, 0.0, 0.0],
                    scale=[sc.collar_diameter_m, sc.collar_diameter_m, sc.collar_height_m],
                )

        n_ok = sum(1 for c in self.components if c.ok)
        self.log(f"[outfall_scene] built {n_ok}/{len(self.components)} components")
        return self.components

    def _spawn(self, kind: str, prop_type: str, critical: bool,
               location: List[float], rotation: List[float], scale: List[float]) -> None:
        comp = SpawnedComponent(kind=kind, prop_type=prop_type,
                                location=[round(v, 3) for v in location],
                                rotation=[round(v, 3) for v in rotation],
                                scale=list(scale), critical=critical, ok=False)
        try:
            self.env.spawn_prop(prop_type, location=location, rotation=rotation,
                                scale=scale, sim_physics=False,
                                material=self.scene.material)
            comp.ok = True
        except Exception as exc:  # engine-side failure
            comp.error = str(exc)
            if critical:
                self.components.append(comp)
                raise SceneBuildError(f"critical component '{kind}' failed: {exc}") from exc
            self.log(f"[outfall_scene] cosmetic component '{kind}' failed: {exc}")
        self.components.append(comp)

    # ------------------------------------------------------------------ #
    def save_manifest(self, path: Union[str, Path]) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        manifest = {
            "outfall": {"x": self.outfall.x, "y": self.outfall.y,
                        "axis_deg": self.outfall.axis_deg,
                        "n_ports": self.outfall.n_ports,
                        "port_spacing_m": self.outfall.port_spacing_m},
            "acoustic_note": "spawned props are visual/collision only; NOT in "
                             "the HoloOcean acoustic octree (verified)",
            "components": [c.__dict__ for c in self.components],
        }
        path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return path

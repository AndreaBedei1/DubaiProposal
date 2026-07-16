"""Multiport desalination outfall scene generator (v2).

Builds a visually credible, engineering-coherent outfall system from
HoloOcean primitives (box / cylinder / cone / sphere + stock materials):

    shore side                                            open sea
    ───────────────►  structure axis (yaw)  ────────────────►
    [semi-buried approach pipeline + flanges + rock berm]
        → [transition collar, pipe ramps up]
            → [exposed diffuser pipe on concrete sleepers]
                → [risers with collars + inclined alternating nozzles]
                    → [end cap]

Every component is defined in a LOCAL frame (s = metres along the axis from
the diffuser start, t = lateral offset, h = height above the local seabed or
above the pipe centreline) and transformed to world coordinates in exactly
one place. Component depths follow the measured terrain (TerrainMap), with a
robust-plane fallback where soundings hit foreign structures.

The geometry is visual + collision only: with the OFFICIAL engine it is NOT
in the acoustic octree (proven experimentally); the custom octree-rebuild
engine makes it sonar-visible (see docs/application/pfh2026/SONAR_VALIDATION.md).
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Tuple, Union

import numpy as np

from ..utils.config import OutfallConfig
from ..utils.terrain import TerrainMap


class SceneBuildError(RuntimeError):
    """A mission-critical scene component could not be spawned."""


class SceneConfigError(ValueError):
    """The outfall geometry configuration is physically invalid."""


def prop_rotation_for_axis(ax: float, ay: float, az: float) -> List[float]:
    """Rotation triple that makes a spawned prop's long axis point along (ax, ay, az).

    HoloOcean's ``spawn_prop`` documents ``rotation`` as ``[roll, pitch, yaw]``,
    but the engine-side SpawnProp command feeds the triple into UE's
    ``Conv_VectorToRotator``: the values are treated as a DIRECTION VECTOR and
    the prop's local +X axis is oriented along it (roll is always 0). This was
    established empirically with calibration renders (23 poses, plan + side
    views) and confirmed in the engine source blueprint cache
    (``SpawnPropCommand`` calls ``KismetMathLibrary:Conv_VectorToRotator``).

    For cylinders/cones the LONG axis is local +Z. With the rotator produced
    by a direction ``d`` = (yaw ``w`` = atan2(dy, dx), pitch ``p`` =
    atan2(dz, hypot(dx, dy)), roll 0), the prop's +Z axis lands on
    ``(-cos w sin p, -sin w sin p, cos p)``. Inverting that for a requested
    axis (tilt-from-vertical ``tau``, horizontal heading ``psi``) gives

        d = (-cos(psi) cos(tau), -sin(psi) cos(tau), sin(tau))

    ``tau`` is capped at 89.7 deg because an exactly horizontal request makes
    the horizontal part of ``d`` vanish and the heading is lost
    (atan2(0, 0) == 0). The residual 0.3 deg tilt is ~1.3 cm over a 2.5 m
    segment — invisible.

    Args:
        ax, ay, az: desired long-axis direction (any magnitude, world frame).

    Returns:
        The ``rotation`` list to pass to ``spawn_prop``.
    """
    n = math.sqrt(ax * ax + ay * ay + az * az)
    if n < 1e-9:
        return [0.0, 0.0, 0.0]
    vx, vy, vz = ax / n, ay / n, az / n
    if vz < 0.0:  # long axis has no sign; keep tau in [0, 90]
        vx, vy, vz = -vx, -vy, -vz
    tau = math.acos(max(-1.0, min(1.0, vz)))
    if tau < math.radians(0.05):
        return [0.0, 0.0, 0.0]  # vertical: zero vector -> zero rotator
    psi = math.atan2(vy, vx)
    tau = min(tau, math.radians(89.7))
    return [-math.cos(psi) * math.cos(tau) * 100.0,
            -math.sin(psi) * math.cos(tau) * 100.0,
            math.sin(tau) * 100.0]


@dataclass
class OutfallSceneConfig:
    """Parametric multiport outfall geometry (dimensions in metres)."""

    # --- main pipeline (approach section, semi-buried) -------------------- #
    pipe_length_m: float = 30.0  # approach length before the diffuser
    pipe_diameter_m: float = 0.9
    # Short segments so the pipeline follows undulating terrain instead of
    # chording under bumps (visual lesson from inspection iteration 3).
    pipe_segment_m: float = 2.5
    embed_fraction: float = 0.35  # fraction of diameter buried in the approach
    flange_scale: float = 1.32  # flange diameter multiplier at segment joints
    flange_length_m: float = 0.26

    # --- diffuser section (exposed, on sleepers) --------------------------- #
    n_risers: int = 6
    riser_spacing_m: float = 3.2
    riser_diameter_m: float = 0.38
    riser_height_m: float = 1.1  # above the diffuser pipe centreline
    riser_collar_scale: float = 1.55
    riser_collar_length_m: float = 0.22
    nozzle_diameter_m: float = 0.22
    nozzle_length_m: float = 0.78
    nozzle_elevation_deg: float = 55.0  # above horizontal
    nozzle_alternate_sides: bool = True
    nozzle_side_yaw_deg: float = 90.0  # discharge direction vs structure axis
    diffuser_margin_m: float = 1.8  # pipe before first / after last riser

    # --- supports and protection ------------------------------------------ #
    sleeper_spacing_m: float = 4.8
    sleeper_size_m: Tuple[float, float, float] = (2.0, 0.75, 0.4)  # across, along, high
    berm_rocks_per_m: float = 1.1  # rock density flanking the buried approach
    berm_rock_scale_m: float = 0.55
    berm_seed: int = 7
    gravel_pad: bool = True  # low gravel disks under the diffuser section
    # Ambient set dressing: a few natural rocks scattered around the site so
    # a featureless world (FlatUnderwater) does not look sterile.
    scatter_rocks: int = 12
    scatter_radius_m: float = 30.0

    # --- finishing --------------------------------------------------------- #
    end_cap: bool = True
    transition_collar: bool = True

    # --- placement / frame -------------------------------------------------- #
    structure_yaw_deg: Optional[float] = None  # None -> from mission config axis
    seabed_offset_m: float = 0.0  # global vertical trim

    # --- materials (HoloOcean stock) ---------------------------------------- #
    material_pipe: str = "steel"
    material_accents: str = "black"  # flanges, transition collar, end cap
    material_hardware: str = "gold"  # riser collars + nozzle tips (brass fittings)
    material_concrete: str = "white"  # sleepers, gravel pad
    material_rock: str = "cobblestone"

    # --- terrain probe (calibration pass) ----------------------------------- #
    probe_half_extent_m: float = 24.0
    probe_spacing_m: float = 6.0
    probe_hold_z_m: float = 8.0

    def validate(self) -> None:
        if not (2 <= self.n_risers <= 10):
            raise SceneConfigError(f"n_risers={self.n_risers} outside [2, 10]")
        if self.riser_spacing_m < 2.0 * self.riser_diameter_m:
            raise SceneConfigError("riser spacing too small vs riser diameter")
        if not (10.0 <= self.nozzle_elevation_deg <= 80.0):
            raise SceneConfigError("nozzle elevation must be in [10, 80] deg")
        if self.pipe_length_m < 2 * self.pipe_segment_m:
            raise SceneConfigError("approach pipeline must span >= 2 segments")
        if not (0.0 <= self.embed_fraction <= 0.49):
            raise SceneConfigError("embed_fraction must be in [0, 0.49]")
        if self.sleeper_size_m[2] <= 0.15:
            raise SceneConfigError("sleepers too thin to read as supports")

    @property
    def diffuser_length_m(self) -> float:
        return (self.n_risers - 1) * self.riser_spacing_m + 2 * self.diffuser_margin_m


@dataclass
class SpawnedComponent:
    kind: str
    prop_type: str
    location: List[float]
    rotation: List[float]
    scale: List[float]
    material: str
    critical: bool
    ok: bool
    error: str = ""


class OutfallSceneBuilder:
    """Builds the multiport outfall in a live HoloOcean environment.

    The structure runs along ``structure_yaw`` with its LOCAL ORIGIN at the
    diffuser start: the approach pipeline occupies s in [-pipe_length, 0],
    the diffuser occupies s in [0, diffuser_length]."""

    def __init__(
        self,
        env,
        agent_name: str,
        outfall: OutfallConfig,
        scene: Optional[OutfallSceneConfig] = None,
        terrain: Optional[TerrainMap] = None,
        upstream_dir_rad: float = math.pi,  # legacy arg: direction TOWARD shore
        log: Callable[[str], None] = print,
        spawn_fn: Optional[Callable] = None,
    ):
        self.env = env
        self.agent_name = agent_name
        self.outfall = outfall
        self.scene = scene or OutfallSceneConfig()
        self.scene.validate()
        self.terrain = terrain
        self.log = log
        # Pluggable spawn backend: default = env.spawn_prop (official engine,
        # direction-vector rotation quirk); the custom engine injects a
        # SpawnAsset-based spawner here (see simulation/custom_engine.py).
        self.spawn_fn = spawn_fn
        self.components: List[SpawnedComponent] = []
        # Structure axis: shore -> sea. The legacy upstream_dir points toward
        # shore, so the axis is its opposite unless explicitly configured.
        yaw = (self.scene.structure_yaw_deg
               if self.scene.structure_yaw_deg is not None
               else math.degrees(upstream_dir_rad) + 180.0)
        self._yaw_rad = math.radians(yaw)
        self._e_s = (math.cos(self._yaw_rad), math.sin(self._yaw_rad))
        self._e_t = (-math.sin(self._yaw_rad), math.cos(self._yaw_rad))
        self._rng = np.random.default_rng(self.scene.berm_seed)

    # ------------------------------------------------------------------ #
    # Local frame
    # ------------------------------------------------------------------ #
    def to_world(self, s: float, t: float) -> Tuple[float, float]:
        """Local (s, t) -> world (x, y). Origin = diffuser start = outfall x/y."""
        return (self.outfall.x + self._e_s[0] * s + self._e_t[0] * t,
                self.outfall.y + self._e_s[1] * s + self._e_t[1] * t)

    def bed(self, s: float, t: float = 0.0) -> float:
        """Measured seabed z at local (s, t) with plane fallback near foreign
        structures (soundings that hit them would float/bury components)."""
        if self.terrain is None:
            raise SceneBuildError("no terrain model: call probe_terrain() or pass one")
        if not hasattr(self, "_plane"):
            self._plane = self.terrain.fit_plane(robust=True)
        x, y = self.to_world(s, t)
        z_map = float(self.terrain.z(x, y))
        z_plane = float(self._plane.z(x, y))
        z = z_plane if abs(z_map - z_plane) > 3.0 else z_map
        return z + self.scene.seabed_offset_m

    def pipe_center_h(self, s: float) -> float:
        """Height of the pipe centreline above the local bed at station s.

        Approach (s < -ramp): semi-buried. Diffuser (s >= 0): proud, resting
        on sleepers. One segment of ramp in between."""
        sc = self.scene
        buried = sc.pipe_diameter_m * (0.5 - sc.embed_fraction)
        proud = sc.sleeper_size_m[2] + sc.pipe_diameter_m / 2.0
        ramp = sc.pipe_segment_m
        if s <= -ramp:
            return buried
        if s >= 0.0:
            return proud
        frac = (s + ramp) / ramp
        return buried + frac * (proud - buried)

    def pipe_center_z(self, s: float) -> float:
        """Pipe centreline z at station s (smoothed node chain when built)."""
        if hasattr(self, "_node_s"):
            return float(np.interp(s, self._node_s, self._node_z))
        return self.bed(s) + self.pipe_center_h(s)

    def _build_node_chain(self) -> None:
        """Precompute the pipeline centreline as a chain of shared nodes.

        Adjacent segments share node positions (no sawtooth joints), and a
        light moving average keeps the pitch profile smooth over probe noise
        (visual lessons from inspection iterations 3-4)."""
        sc = self.scene
        step = sc.pipe_segment_m
        s_vals = np.arange(-sc.pipe_length_m, sc.diffuser_length_m + step / 2, step)
        z_raw = np.array([self.bed(s) + self.pipe_center_h(s) for s in s_vals])
        z_smooth = z_raw.copy()
        for i in range(1, len(z_raw) - 1):
            z_smooth[i] = 0.25 * z_raw[i - 1] + 0.5 * z_raw[i] + 0.25 * z_raw[i + 1]
        # Engineering grade limit: real pipelines are laid with cut-and-fill,
        # not draped over every bump — clamp the slope to +-max_grade.
        max_grade = math.tan(math.radians(12.0))
        for i in range(1, len(z_smooth)):
            dz = z_smooth[i] - z_smooth[i - 1]
            limit = max_grade * (s_vals[i] - s_vals[i - 1])
            z_smooth[i] = z_smooth[i - 1] + max(-limit, min(limit, dz))
        self._node_s = s_vals
        self._node_z = z_smooth

    # ------------------------------------------------------------------ #
    # Terrain calibration (unchanged public API)
    # ------------------------------------------------------------------ #
    def probe_terrain(self, reference_bed_z: float,
                      xs: Optional[np.ndarray] = None,
                      ys: Optional[np.ndarray] = None) -> TerrainMap:
        """Sound the bottom on a grid with the down-looking RangeFinder."""
        sc = self.scene
        cx, cy = self.outfall.x, self.outfall.y
        if xs is None:
            xs = np.arange(cx - sc.probe_half_extent_m, cx + sc.probe_half_extent_m + 1e-6,
                           sc.probe_spacing_m)
        if ys is None:
            ys = np.arange(cy - sc.probe_half_extent_m, cy + sc.probe_half_extent_m + 1e-6,
                           sc.probe_spacing_m)
        xs = np.asarray(xs, dtype=float)
        ys = np.asarray(ys, dtype=float)
        hold_z = reference_bed_z + sc.probe_hold_z_m
        agent = self.env.agents[self.agent_name]
        grid = np.full((len(ys), len(xs)), np.nan)
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
                    grid[i, j] = z - float(valid.min())
        self.terrain = TerrainMap(xs, ys, grid)
        self.log(f"[outfall_scene] terrain probe: bed z in "
                 f"[{np.nanmin(grid):.2f}, {np.nanmax(grid):.2f}] over "
                 f"{len(xs)}x{len(ys)} soundings")
        return self.terrain

    # ------------------------------------------------------------------ #
    def auto_orient(self, span_m: Optional[float] = None, n_dirs: int = 24) -> float:
        """Choose the structure yaw that minimises terrain height variance
        along the pipeline line — real outfalls follow gentle grades, and it
        keeps the pipe visually continuous on undulating seabeds.

        Returns the chosen yaw (deg) and updates the internal frame."""
        if self.terrain is None:
            raise SceneBuildError("auto_orient requires a terrain model")
        sc = self.scene
        span = span_m or (sc.pipe_length_m + sc.diffuser_length_m)
        best = (None, None, float("inf"))  # (yaw, origin, height range)
        for dx in (-8.0, 0.0, 8.0):
            for dy in (-8.0, 0.0, 8.0):
                o = (self.outfall.x + dx, self.outfall.y + dy)
                for k in range(n_dirs):
                    yaw = k * (360.0 / n_dirs)
                    e = (math.cos(math.radians(yaw)), math.sin(math.radians(yaw)))
                    ss = np.linspace(-sc.pipe_length_m, span - sc.pipe_length_m, 25)
                    zs = np.array([float(self.terrain.z(o[0] + e[0] * s,
                                                        o[1] + e[1] * s)) for s in ss])
                    rng = float(zs.max() - zs.min())
                    if rng < best[2]:
                        best = (yaw, o, rng)
        best_yaw, origin, best_rng = best
        self.outfall.x, self.outfall.y = origin
        self._yaw_rad = math.radians(best_yaw)
        self._e_s = (math.cos(self._yaw_rad), math.sin(self._yaw_rad))
        self._e_t = (-math.sin(self._yaw_rad), math.cos(self._yaw_rad))
        self.log(f"[outfall_scene] auto-orient: yaw {best_yaw:.0f} deg, origin "
                 f"({origin[0]:.1f}, {origin[1]:.1f}), height range "
                 f"{best_rng:.2f} m along the line")
        return best_yaw

    # ------------------------------------------------------------------ #
    # Build
    # ------------------------------------------------------------------ #
    def build(self) -> List[SpawnedComponent]:
        sc = self.scene
        self._build_node_chain()

        # ---- approach pipeline: semi-buried segments + flanges + berm ---- #
        n_seg = int(round(sc.pipe_length_m / sc.pipe_segment_m))
        for k in range(n_seg):
            s1 = -sc.pipe_length_m + k * sc.pipe_segment_m
            s2 = s1 + sc.pipe_segment_m
            self._pipe_segment(f"approach_pipe_{k}", s1, s2, critical=(k >= n_seg - 2))
            if k > 0 and k % 2 == 0:
                self._flange(f"approach_flange_{k}", s1)
        self._berm()

        # ---- transition collar where the pipe leaves the seabed ---------- #
        if sc.transition_collar:
            self._collar("transition_collar", -sc.pipe_segment_m / 2.0,
                         scale=sc.flange_scale * 1.15, critical=False)

        # ---- diffuser pipe on sleepers ----------------------------------- #
        L = sc.diffuser_length_m
        n_dseg = max(1, int(math.ceil(L / sc.pipe_segment_m)))
        dseg = L / n_dseg
        for k in range(n_dseg):
            self._pipe_segment(f"diffuser_pipe_{k}", k * dseg, (k + 1) * dseg,
                               critical=True)
        n_sleep = int(L / sc.sleeper_spacing_m) + 1
        for k in range(n_sleep):
            self._sleeper(f"sleeper_{k}", min(k * sc.sleeper_spacing_m + 0.8, L - 0.8))
        if sc.gravel_pad:
            self._gravel_pad()

        # ---- risers + collars + nozzles ---------------------------------- #
        for k in range(sc.n_risers):
            s = sc.diffuser_margin_m + k * sc.riser_spacing_m
            side = 1.0 if (not sc.nozzle_alternate_sides or k % 2 == 0) else -1.0
            self._riser(k, s, side)

        # ---- end cap ------------------------------------------------------ #
        if sc.end_cap:
            s_end = L + 0.35
            self._spawn("end_cap", "cone", critical=False,
                        location=self._at(s_end, 0.0, self.pipe_center_z(L)),
                        rotation=prop_rotation_for_axis(
                            math.cos(self._yaw_rad), math.sin(self._yaw_rad), 0.0),
                        scale=[sc.pipe_diameter_m * 1.05, sc.pipe_diameter_m * 1.05, 0.8],
                        material=sc.material_accents)

        # ---- ambient rocks (set dressing, never on the structure line) ---- #
        for k in range(sc.scatter_rocks):
            ang = float(self._rng.uniform(0, 2 * math.pi))
            rad = float(self._rng.uniform(10.0, sc.scatter_radius_m))
            s = rad * math.cos(ang)
            t = rad * math.sin(ang)
            if abs(t) < 4.0:  # keep the structure corridor clear
                t = math.copysign(4.0 + abs(t), t if t != 0 else 1.0)
            r = float(self._rng.uniform(0.3, 0.9))
            rock_hdg = float(self._rng.uniform(0, 2 * math.pi))
            self._spawn(f"ambient_rock_{k}", "sphere", critical=False,
                        location=self._at(s, t, self.bed(s, t) + r * 0.35),
                        rotation=prop_rotation_for_axis(math.cos(rock_hdg),
                                                        math.sin(rock_hdg), 0.0),
                        scale=[r, r * float(self._rng.uniform(0.7, 1.0)), r * 0.65],
                        material=sc.material_rock)

        n_ok = sum(1 for c in self.components if c.ok)
        self.log(f"[outfall_scene] built {n_ok}/{len(self.components)} components "
                 f"({sc.n_risers} risers, {n_seg}+{n_dseg} pipe segments)")
        return self.components

    # ------------------------------------------------------------------ #
    # Component builders (all positions via the local frame)
    # ------------------------------------------------------------------ #
    def _at(self, s: float, t: float, z: float) -> List[float]:
        x, y = self.to_world(s, t)
        return [x, y, z]

    def _axis_along(self, s1: float, s2: float) -> Tuple[float, float, float]:
        """World direction of the pipe centreline between two s-nodes."""
        z1, z2 = self.pipe_center_z(s1), self.pipe_center_z(s2)
        grade = math.atan2(z2 - z1, max(s2 - s1, 1e-6))
        cg = math.cos(grade)
        return (cg * math.cos(self._yaw_rad), cg * math.sin(self._yaw_rad),
                math.sin(grade))

    def _pipe_segment(self, kind: str, s1: float, s2: float, critical: bool) -> None:
        sc = self.scene
        sm = (s1 + s2) / 2.0
        # Node-chain geometry: both endpoints are SHARED nodes, so adjacent
        # segments meet exactly (no sawtooth joints, no gaps).
        z1, z2 = self.pipe_center_z(s1), self.pipe_center_z(s2)
        zm = (z1 + z2) / 2.0
        length = math.hypot(s2 - s1, z2 - z1)
        self._spawn(kind, "cylinder", critical=critical,
                    location=self._at(sm, 0.0, zm),
                    rotation=prop_rotation_for_axis(*self._axis_along(s1, s2)),
                    scale=[sc.pipe_diameter_m, sc.pipe_diameter_m, length + 0.25],
                    material=sc.material_pipe)

    def _flange(self, kind: str, s: float) -> None:
        sc = self.scene
        self._collar(kind, s, scale=sc.flange_scale, critical=False)

    def _collar(self, kind: str, s: float, scale: float, critical: bool) -> None:
        sc = self.scene
        d = sc.pipe_diameter_m * scale
        # follow the local pipe slope so collars sit flush on the ramp
        self._spawn(kind, "cylinder", critical=critical,
                    location=self._at(s, 0.0, self.pipe_center_z(s)),
                    rotation=prop_rotation_for_axis(*self._axis_along(s - 0.4, s + 0.4)),
                    scale=[d, d, sc.flange_length_m],
                    material=sc.material_accents)

    def _sleeper(self, kind: str, s: float) -> None:
        sc = self.scene
        w_across, w_along, h = sc.sleeper_size_m
        # box local +X points along the requested direction (roll stays 0):
        # aim X across the pipe so the sleeper lies perpendicular under it
        across = self._yaw_rad + math.pi / 2.0
        self._spawn(kind, "box", critical=False,
                    location=self._at(s, 0.0, self.bed(s) + h / 2.0),
                    rotation=prop_rotation_for_axis(math.cos(across),
                                                    math.sin(across), 0.0),
                    scale=[w_across, w_along, h],
                    material=sc.material_concrete)

    def _gravel_pad(self) -> None:
        """Low scour-protection pads under the diffuser (flat rock disks —
        cylinders lie flat with no rotation, the safest primitive)."""
        sc = self.scene
        L = sc.diffuser_length_m
        n = max(3, int(L / 4.5))
        for k in range(n):
            s = (k + 0.5) * L / n
            self._spawn(f"gravel_pad_{k}", "cylinder", critical=False,
                        location=self._at(s, 0.0, self.bed(s) + 0.05),
                        rotation=[0.0, 0.0, 0.0],
                        scale=[3.6, 3.6, 0.10],
                        material=sc.material_rock)

    def _riser(self, index: int, s: float, side: float) -> None:
        sc = self.scene
        yaw_deg = math.degrees(self._yaw_rad)
        pipe_z = self.pipe_center_z(s)
        top_z = pipe_z + sc.riser_height_m

        # riser barrel: from the pipe centreline up (visually connected)
        self._spawn(f"riser_{index}", "cylinder", critical=True,
                    location=self._at(s, 0.0, (pipe_z + top_z) / 2.0),
                    rotation=[0.0, 0.0, 0.0],
                    scale=[sc.riser_diameter_m, sc.riser_diameter_m,
                           sc.riser_height_m + sc.pipe_diameter_m * 0.4],
                    material=sc.material_pipe)
        # base collar where the riser meets the pipe
        self._spawn(f"riser_collar_{index}", "cylinder", critical=False,
                    location=self._at(s, 0.0, pipe_z + sc.pipe_diameter_m * 0.45),
                    rotation=[0.0, 0.0, 0.0],
                    scale=[sc.riser_diameter_m * sc.riser_collar_scale,
                           sc.riser_diameter_m * sc.riser_collar_scale,
                           sc.riser_collar_length_m],
                    material=sc.material_hardware)

        # inclined discharge nozzle across the structure axis (+-t side)
        nozzle_yaw = yaw_deg + side * sc.nozzle_side_yaw_deg
        # unit vector of the nozzle axis (for placing barrel + tip)
        el = math.radians(sc.nozzle_elevation_deg)
        dir_x = math.cos(el) * math.cos(math.radians(nozzle_yaw))
        dir_y = math.cos(el) * math.sin(math.radians(nozzle_yaw))
        dir_z = math.sin(el)
        nozzle_rot = prop_rotation_for_axis(dir_x, dir_y, dir_z)
        half = sc.nozzle_length_m / 2.0
        bx, by = self.to_world(s, 0.0)
        base = (bx, by, top_z)
        self._spawn(f"nozzle_{index}", "cylinder", critical=True,
                    location=[base[0] + dir_x * half, base[1] + dir_y * half,
                              base[2] + dir_z * half],
                    rotation=nozzle_rot,
                    scale=[sc.nozzle_diameter_m, sc.nozzle_diameter_m,
                           sc.nozzle_length_m],
                    material=sc.material_pipe)
        tip = sc.nozzle_length_m + 0.06
        self._spawn(f"nozzle_tip_{index}", "cone", critical=False,
                    location=[base[0] + dir_x * tip, base[1] + dir_y * tip,
                              base[2] + dir_z * tip],
                    rotation=nozzle_rot,
                    scale=[sc.nozzle_diameter_m * 1.15, sc.nozzle_diameter_m * 1.15,
                           0.22],
                    material=sc.material_hardware)

    def _berm(self) -> None:
        """Rock protection flanking the buried approach pipeline."""
        sc = self.scene
        n = int(sc.pipe_length_m * sc.berm_rocks_per_m)
        for k in range(n):
            s = -self._rng.uniform(sc.pipe_segment_m * 0.8, sc.pipe_length_m)
            side = 1.0 if k % 2 == 0 else -1.0
            t = side * (sc.pipe_diameter_m * 0.85 + self._rng.uniform(0.0, 0.7))
            # small, half-sunken, flattened rocks (big proud spheres read as
            # naval mines with the cobblestone texture — iteration 8 lesson)
            r = sc.berm_rock_scale_m * self._rng.uniform(0.45, 0.95)
            rock_hdg = float(self._rng.uniform(0, 2 * math.pi))
            self._spawn(f"berm_rock_{k}", "sphere", critical=False,
                        location=self._at(s, t, self.bed(s, t) + r * 0.12),
                        rotation=prop_rotation_for_axis(math.cos(rock_hdg),
                                                        math.sin(rock_hdg), 0.0),
                        scale=[r, r * self._rng.uniform(0.7, 1.0), r * 0.5],
                        material=sc.material_rock)

    # ------------------------------------------------------------------ #
    def _spawn(self, kind: str, prop_type: str, critical: bool,
               location: List[float], rotation: List[float], scale: List[float],
               material: str) -> None:
        comp = SpawnedComponent(kind=kind, prop_type=prop_type,
                                location=[round(v, 3) for v in location],
                                rotation=[round(v, 3) for v in rotation],
                                scale=[round(v, 3) for v in scale],
                                material=material, critical=critical, ok=False)
        try:
            spawn = self.spawn_fn or self.env.spawn_prop
            spawn(prop_type, location=location, rotation=rotation,
                  scale=scale, sim_physics=False, material=material)
            comp.ok = True
        except Exception as exc:
            comp.error = str(exc)
            if critical:
                self.components.append(comp)
                raise SceneBuildError(f"critical component '{kind}' failed: {exc}") from exc
            self.log(f"[outfall_scene] cosmetic component '{kind}' failed: {exc}")
        self.components.append(comp)

    def save_manifest(self, path: Union[str, Path]) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        sc = self.scene
        manifest = {
            "design": "multiport diffuser outfall v2 (local-frame parametric)",
            "origin_world": [self.outfall.x, self.outfall.y],
            "structure_yaw_deg": round(math.degrees(self._yaw_rad), 2),
            "pipe": {"length_m": sc.pipe_length_m, "diameter_m": sc.pipe_diameter_m,
                     "embed_fraction": sc.embed_fraction},
            "diffuser": {"length_m": round(sc.diffuser_length_m, 2),
                         "n_risers": sc.n_risers,
                         "riser_spacing_m": sc.riser_spacing_m,
                         "riser_height_m": sc.riser_height_m,
                         "nozzle_elevation_deg": sc.nozzle_elevation_deg},
            "acoustic_note": "props are in the octree ONLY with the custom "
                             "octree-rebuild engine; invisible to official "
                             "HoloOcean sonar (verified)",
            "components": [c.__dict__ for c in self.components],
        }
        path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return path

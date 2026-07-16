"""Mission state machine: LOCATE -> BASELINE -> SURVEY -> DONE.

The runner owns the travel budget, the CTD sampling, the GP mapper and the
mission log; the backend only moves the vehicle, and the planner only picks
waypoints. LOCATE and BASELINE are identical for every planner, so the
lawnmower-vs-adaptive comparison differs only in the SURVEY phase, at equal
total budget.
"""
from __future__ import annotations

import math
import time
from typing import Callable, Optional, Tuple

import numpy as np

from ..mapping.gp_mapper import GPMapper
from ..planning.adaptive import AdaptivePlanner
from ..planning.base import Planner
from ..planning.lawnmower import LawnmowerPlanner
from ..plume.model import BrinePlume
from ..sensors.ctd import VirtualCTD
from ..sensors.locator import DiffuserLocator
from ..simulation import make_backend
from ..simulation.base import SimulatorBackend
from ..utils.config import MissionConfig
from ..utils.geometry import dist3, expanding_square
from ..utils.logging_utils import MissionLogger
from ..utils.types import (
    MissionBudget,
    MissionPhase,
    MissionResult,
    VehicleState,
    Waypoint,
)


def boundary_salinity_psu(cfg: MissionConfig, plume: BrinePlume) -> float:
    """Compliance threshold: ambient near-bottom salinity at the outfall,
    increased by the configured percentage."""
    bed_z = float(plume.seabed_z(cfg.outfall.x, cfg.outfall.y))
    ambient_bottom = float(plume.ambient_salinity(bed_z))
    return ambient_bottom * (1.0 + cfg.compliance.threshold_increment_pct / 100.0)


def build_locator(cfg: MissionConfig, plume: BrinePlume):
    """Build the localization source selected by ``cfg.locator.mode``.

    - "synthetic": oracle-fed detection model (kinematic baselines only).
    - "sonar": real ImagingSonar pipeline — NO ground-truth access; requires
      the HoloOcean backend with ``backend.holoocean.sonar_enabled: true``.
    """
    mode = cfg.locator.mode
    if mode == "synthetic":
        return DiffuserLocator(cfg.locator, plume.outfall_xy(), seed=cfg.seed + 23)
    if mode == "sonar":
        from ..perception.sonar_diffuser_detector import DetectorConfig
        from ..perception.sonar_localizer import SonarDiffuserLocator, SonarLocalizerConfig

        if cfg.backend.name == "holoocean" and not cfg.backend.holoocean.sonar_enabled:
            raise ValueError(
                "locator.mode='sonar' requires backend.holoocean.sonar_enabled: true"
            )
        prior = None
        if cfg.locator.prior_x is not None and cfg.locator.prior_y is not None:
            prior = (float(cfg.locator.prior_x), float(cfg.locator.prior_y))
        return SonarDiffuserLocator(SonarLocalizerConfig(
            # Gates tuned on RECORDED noisy mission data (detector_eval): in
            # noise, contact strength no longer separates structure from
            # clutter (distributions overlap), so the burden moves to spatial
            # persistence — the densest multi-aspect cluster of world
            # estimates near the chart prior.
            detector=DetectorConfig(min_range_m=8.0),
            min_strength=6.0,
            min_hits_for_consensus=10,
            prior_xy=prior,
            prior_gate_m=2.0 * cfg.locator.prior_sigma_m,
        ))
    raise ValueError(f"Unknown locator mode '{mode}' (expected 'synthetic' or 'sonar')")


def build_planner(name: str, cfg: MissionConfig, plume: BrinePlume) -> Planner:
    seabed = lambda x, y: float(plume.seabed_z(x, y))  # noqa: E731
    if name == "lawnmower":
        return LawnmowerPlanner(cfg.survey, cfg.lawnmower, seabed)
    if name == "adaptive":
        return AdaptivePlanner(
            cfg.survey,
            cfg.adaptive,
            boundary_salinity_psu(cfg, plume),
            seabed,
            seed=cfg.seed + 101,
        )
    raise ValueError(f"Unknown planner '{name}' (expected 'lawnmower' or 'adaptive')")


class MissionRunner:
    def __init__(
        self,
        cfg: MissionConfig,
        backend: SimulatorBackend,
        planner: Planner,
        plume: BrinePlume,
        ctd: VirtualCTD,
        locator,  # SyntheticDiffuserLocator | SonarDiffuserLocator (observe() protocol)
        mapper: GPMapper,
        logger: Optional[MissionLogger] = None,
        sonar_recorder=None,  # optional brinewatch.sensors.sonar_recorder.SonarRecorder
    ):
        self.cfg = cfg
        self.backend = backend
        self.planner = planner
        self.plume = plume
        self.ctd = ctd
        self.locator = locator
        self.mapper = mapper
        self.logger = logger
        self.sonar_recorder = sonar_recorder
        self._rng = np.random.default_rng(cfg.seed)
        self.result = MissionResult(planner_name=planner.name)
        self.budget = MissionBudget(cfg.budget.max_distance_m)
        self.result.budget = self.budget
        self._state: Optional[VehicleState] = None
        self._phase = MissionPhase.LOCATE
        self._collision_count = 0
        self._was_colliding = False
        # (x, y) of waypoints that stalled: unreachable spots keep high GP
        # uncertainty and would be re-proposed forever by adaptive planners.
        self._stalled_xy: list = []

    # ------------------------------------------------------------------ #
    def run(self) -> MissionResult:
        t_start = time.perf_counter()
        self._state = self.backend.reset()
        self._record_trajectory()
        self._log("mission_start", planner=self.planner.name,
                  backend=self.backend.name, seed=self.cfg.seed,
                  budget_m=self.budget.max_distance_m)

        outfall_xy = self._phase_locate()
        self._phase_baseline(outfall_xy)
        self._phase_survey()

        self._set_phase(MissionPhase.DONE)
        self.result.wall_time_s = time.perf_counter() - t_start
        if self._collision_count:
            self.result.notes.append(f"{self._collision_count} collision event(s) detected")
        self._log("mission_end", n_samples=len(self.result.samples),
                  budget_used_m=round(self.budget.used_m, 1),
                  collisions=self._collision_count,
                  wall_time_s=round(self.result.wall_time_s, 2))
        return self.result

    # ------------------------------------------------------------------ #
    # Phases
    # ------------------------------------------------------------------ #
    def _phase_locate(self) -> Tuple[float, float]:
        """Search for the diffuser around the a-priori outfall position."""
        self._set_phase(MissionPhase.LOCATE)
        if self.cfg.locator.prior_x is not None and self.cfg.locator.prior_y is not None:
            # Explicit chart prior from configuration: the official no-leakage
            # path — nothing here reads the true outfall position.
            prior = (float(self.cfg.locator.prior_x), float(self.cfg.locator.prior_y))
            self._log("locate_prior", prior=prior, source="config")
        else:
            # Kinematic-baseline convenience: synthesize chart error around the
            # true position (documented; not used in official evidence runs).
            true_xy = self.plume.outfall_xy()
            prior = (
                true_xy[0] + float(self._rng.normal(0.0, self.cfg.locator.prior_sigma_m)),
                true_xy[1] + float(self._rng.normal(0.0, self.cfg.locator.prior_sigma_m)),
            )
            self._log("locate_prior", prior=prior, source="synthesized_from_truth")

        locate_cap_m = self.cfg.budget.locate_fraction * self.budget.max_distance_m
        step = 1.5 * self.cfg.locator.max_range_m
        for wx, wy in expanding_square(prior, step=step, n_legs=14):
            wp = self._survey_waypoint(wx, wy)
            found = self._navigate(wp, ping_locator=True,
                                   stop_after_detections=self.cfg.locator.n_confirm)
            if found == "detected":
                # Prefer the locator's own robust consensus (sonar pipeline);
                # fall back to averaging the confirming detections (synthetic).
                est = getattr(self.locator, "consensus", None)
                if est is None:
                    dets = self.result.detections[-self.cfg.locator.n_confirm:]
                    est = (
                        float(np.mean([d.est_x for d in dets])),
                        float(np.mean([d.est_y for d in dets])),
                    )
                est = (float(est[0]), float(est[1]))
                self.result.outfall_estimate = est
                # No ground-truth access here: localization error is computed
                # only by the post-mission evaluator (see demo/benchmark).
                self._log("outfall_found", estimate=est,
                          n_detections=len(self.result.detections),
                          budget_used_m=round(self.budget.used_m, 1))
                return est
            if self.budget.used_m >= locate_cap_m:
                break
        # Fallback: proceed with the prior (logged honestly)
        self.result.outfall_estimate = prior
        self.result.notes.append("outfall not confirmed by locator; using prior position")
        self._log("outfall_fallback_prior", estimate=prior)
        return prior

    def _phase_baseline(self, outfall_xy: Tuple[float, float]) -> None:
        """Two crossing transects through the outfall estimate: along-current
        and across-current, each spanning the mixing zone."""
        self._set_phase(MissionPhase.BASELINE)
        r = 0.9 * self.cfg.compliance.mixing_zone_radius_m
        theta = math.radians(self.cfg.environment.current_dir_deg)
        e_c = (math.cos(theta), math.sin(theta))
        e_x = (-e_c[1], e_c[0])
        cx, cy = outfall_xy
        # Both transects are offset away from the physical outfall structures
        # (props in the HoloOcean world): the pipe runs along the upstream
        # axis and the diffuser manifold runs along the cross-current axis,
        # so flying either corridor for tens of metres at low clearance
        # invites collisions. 4 m offsets keep the legs well inside the plume
        # (width >= 6 m) but clear of the hardware.
        off = 4.0
        ox, oy = cx + off * e_x[0], cy + off * e_x[1]  # beside the pipe axis
        dx, dy = cx + off * e_c[0], cy + off * e_c[1]  # downstream of the manifold
        legs = [
            (ox - r * e_c[0], oy - r * e_c[1]),
            (ox + 1.5 * r * e_c[0], oy + 1.5 * r * e_c[1]),  # longer downstream leg
            (dx + r * e_x[0], dy + r * e_x[1]),
            (dx - r * e_x[0], dy - r * e_x[1]),
        ]
        for wx, wy in legs:
            if self.budget.exhausted:
                return
            self._navigate(self._survey_waypoint(wx, wy))

    STALL_BLACKLIST_RADIUS_M = 8.0
    MAX_CONSECUTIVE_SKIPS = 25

    def _phase_survey(self) -> None:
        self._set_phase(MissionPhase.SURVEY)
        skips = 0
        while not self.budget.exhausted:
            wp = self.planner.next_waypoint(self._state, self.mapper, self.budget)
            if wp is None:
                self._log("planner_done", budget_used_m=round(self.budget.used_m, 1))
                return
            if self._near_stalled(wp):
                skips += 1
                if skips > self.MAX_CONSECUTIVE_SKIPS:
                    self.result.notes.append("survey ended: planner kept proposing unreachable areas")
                    self._log("planner_blacklist_exhausted")
                    return
                continue
            skips = 0
            # Depth safety ceiling also for planner-generated waypoints
            if wp.z > self.cfg.survey.max_z_m:
                wp = Waypoint(wp.x, wp.y, self.cfg.survey.max_z_m, wp.tolerance)
            draw = getattr(self.backend, "draw_waypoint", None)
            if callable(draw):
                draw(wp)
            if self._navigate(wp) == "stalled":
                self._stalled_xy.append((wp.x, wp.y))

    def _near_stalled(self, wp: Waypoint) -> bool:
        return any(
            math.hypot(wp.x - sx, wp.y - sy) < self.STALL_BLACKLIST_RADIUS_M
            for sx, sy in self._stalled_xy
        )

    # ------------------------------------------------------------------ #
    # Navigation and sensing
    # ------------------------------------------------------------------ #
    # Abort a leg after this many control steps without >0.3 m of progress.
    NO_PROGRESS_STEPS = 80

    def _navigate(
        self,
        wp: Waypoint,
        ping_locator: bool = False,
        stop_after_detections: Optional[int] = None,
    ) -> str:
        """Drive toward ``wp`` until reached / budget out / stalled.

        Returns "reached", "budget", "stalled" or "detected"."""
        assert self._state is not None
        dist = self._state.distance_to(wp)
        # Hard cap: assume at least ~0.15 m/s effective progress
        max_steps = int(dist / (0.15 * self.backend.control_period_s) + 120)
        best_dist = float("inf")
        no_progress = 0

        for _ in range(max_steps):
            if self.budget.exhausted:
                return "budget"
            prev = self._state.position
            self._state = self.backend.step_toward(wp)
            self.budget.consume(dist3(prev, self._state.position))
            self._record_trajectory()

            # Collision accounting (rising edge only, to avoid log spam)
            if self._state.collided and not self._was_colliding:
                self._collision_count += 1
                self._log("collision", t=self._state.t,
                          pos=(round(self._state.x, 1), round(self._state.y, 1),
                               round(self._state.z, 1)),
                          count=self._collision_count)
            self._was_colliding = self._state.collided

            sample = self.ctd.maybe_sample(self._state)
            if sample is not None:
                self.result.samples.append(sample)
                self.result.budget_at_sample.append(self.budget.used_m)
                self.mapper.add_sample(sample)

            if ping_locator:
                det = self.locator.observe(self._state, self._observation())
                if det is not None:
                    self.result.detections.append(det)
                    self._log("detection", t=det.t, range_m=round(det.range_m, 2),
                              est=(round(det.est_x, 1), round(det.est_y, 1)))
                    # Total across the whole LOCATE phase: consensus-gated
                    # sonar detections can arrive one or two per leg.
                    if (stop_after_detections is not None
                            and len(self.result.detections) >= stop_after_detections):
                        return "detected"

            # Arrival is HORIZONTAL-only: the waypoint z is advisory — depth is
            # delegated to the backend's terrain following (real terrain can
            # differ from the analytic plane by metres), and the CTD samples
            # are georeferenced at the *actual* depth, so no bias is introduced.
            horiz = math.hypot(self._state.x - wp.x, self._state.y - wp.y)
            if horiz <= wp.tolerance:
                return "reached"

            # Reactive stall detection: no meaningful progress for a while
            cur = self._state.distance_to(wp)
            if cur < best_dist - 0.3:
                best_dist = cur
                no_progress = 0
            else:
                no_progress += 1
                if no_progress >= self.NO_PROGRESS_STEPS:
                    break

        self.result.notes.append(f"stalled while navigating to ({wp.x:.1f}, {wp.y:.1f})")
        self._log("navigation_stalled", wp=(wp.x, wp.y, wp.z))
        return "stalled"

    def _observation(self) -> Optional[dict]:
        """Fetch the backend's observation bundle (None for backends without
        sensors beyond vehicle state, e.g. the kinematic one). Records sonar
        frames when a recorder is attached."""
        get_obs = getattr(self.backend, "get_observation", None)
        if not callable(get_obs):
            return None
        obs = get_obs()
        if obs and self.sonar_recorder is not None and obs.get("sonar") is not None:
            self.sonar_recorder.add(obs["sonar"])
        return obs

    def _survey_waypoint(self, x: float, y: float) -> Waypoint:
        """Waypoint at survey altitude, clamped inside the survey box.

        LOCATE (expanding square) and BASELINE legs are generated relative to
        the outfall estimate and can otherwise leave the box — and, in small
        worlds like SimpleUnderwater, the playable volume."""
        margin = 2.0
        x = min(max(x, self.cfg.survey.x_min + margin), self.cfg.survey.x_max - margin)
        y = min(max(y, self.cfg.survey.y_min + margin), self.cfg.survey.y_max - margin)
        z = float(self.plume.seabed_z(x, y)) + self.cfg.survey.altitude_m
        z = min(z, self.cfg.survey.max_z_m)  # depth safety ceiling
        return Waypoint(x, y, z)

    def _record_trajectory(self) -> None:
        s = self._state
        self.result.trajectory.append((s.t, s.x, s.y, s.z))

    def _set_phase(self, phase: MissionPhase) -> None:
        self._phase = phase
        t = self._state.t if self._state else 0.0
        self.result.phase_history.append((t, phase.value))
        self._log("phase", phase=phase.value, budget_used_m=round(self.budget.used_m, 1))

    def _log(self, kind: str, **payload) -> None:
        if self.logger is not None:
            self.logger.event(kind, **payload)


# ---------------------------------------------------------------------- #
# Factory
# ---------------------------------------------------------------------- #
def create_mission(
    cfg: MissionConfig,
    planner_name: Optional[str] = None,
    backend_name: Optional[str] = None,
    logger: Optional[MissionLogger] = None,
    seed_offset: int = 0,
    backend: Optional[SimulatorBackend] = None,
    sonar_recorder=None,
) -> MissionRunner:
    """Wire up a full mission from config. ``seed_offset`` lets benchmarks run
    several statistically independent missions from one config. Passing an
    existing ``backend`` reuses a live simulator (e.g. after a terrain-probe
    and scene-build pass in the same engine session)."""
    import dataclasses

    if seed_offset:
        cfg = dataclasses.replace(cfg, seed=cfg.seed + seed_offset)
    planner_name = planner_name or cfg.planner
    backend_name = backend_name or cfg.backend.name

    plume = BrinePlume(cfg.environment, cfg.outfall, cfg.plume)
    planner = build_planner(planner_name, cfg, plume)
    ctd = VirtualCTD(cfg.ctd, plume, seed=cfg.seed + 11)
    locator = build_locator(cfg, plume)
    mapper = GPMapper(cfg.gp, plume.ambient_salinity, seed=cfg.seed + 31)

    if backend is None:
        start = (
            0.5 * (cfg.survey.x_min + cfg.survey.x_max),
            0.5 * (cfg.survey.y_min + cfg.survey.y_max),
            float(plume.seabed_z(0.5 * (cfg.survey.x_min + cfg.survey.x_max),
                                 0.5 * (cfg.survey.y_min + cfg.survey.y_max))) + 8.0,
        )
        backend = make_backend(backend_name, cfg.backend, cfg.environment, cfg.outfall,
                               start, seed=cfg.seed + 41)
    return MissionRunner(cfg, backend, planner, plume, ctd, locator, mapper, logger,
                         sonar_recorder=sonar_recorder)

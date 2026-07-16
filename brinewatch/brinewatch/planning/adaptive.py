"""Adaptive informative sampling planner — greedy GP-based waypoint selection.

Behaviour (greedy informative path planning):
- Candidate set: each call, draw ``cfg.n_candidates`` random 2-D points
  uniformly in the survey box (seeded rng), at
  ``z = seabed_fn(x, y) + survey.altitude_m`` — the same altitude the
  lawnmower flies, for fairness.
- Filter candidates to a travel leg between ``cfg.min_leg_m`` and
  ``cfg.max_leg_m`` from the current position (if none qualify, relax to the
  nearest candidate).
- Score each candidate with the GP posterior at its position:
    score = cfg.weight_std * (std / max_std_among_candidates)
          + cfg.weight_boundary * exp(-|mean - boundary_salinity_psu| / cfg.boundary_scale_psu)
          - cfg.weight_travel * (dist / cfg.max_leg_m)
  The boundary term concentrates effort on the compliance isohaline — the
  plume boundary — which is what the verdict depends on.
- Skip candidates within ``cfg.min_separation_m`` (horizontal) of any point
  already visited by this planner (it keeps an internal list of the waypoints
  it has returned) to avoid resampling the same spot. If the rule filters out
  every remaining candidate, it is ignored for that call.
- Warmup: while ``mapper.n_samples < cfg.warmup_samples``, behave like a
  short exploratory pattern — return random candidates ranked by distance
  from previous picks — rather than trusting an empty GP.
- Budget-awareness: if remaining budget < cfg.min_leg_m, return None.
"""
from __future__ import annotations

from typing import Callable, List, Optional

import numpy as np

from ..mapping.gp_mapper import GPMapper
from ..utils.config import AdaptiveConfig, SurveyConfig
from ..utils.types import MissionBudget, VehicleState, Waypoint
from .base import Planner


class AdaptivePlanner(Planner):
    name = "adaptive"

    def __init__(
        self,
        survey: SurveyConfig,
        cfg: AdaptiveConfig,
        boundary_salinity_psu: float,
        seabed_fn: Callable[[float, float], float],
        seed: int = 0,
    ):
        self.survey = survey
        self.cfg = cfg
        self.boundary_salinity_psu = boundary_salinity_psu
        self.seabed_fn = seabed_fn
        self._rng = np.random.default_rng(seed)
        self._visited_xy: List[np.ndarray] = []  # (x, y) of waypoints we returned

    # ------------------------------------------------------------------ #
    def next_waypoint(
        self, state: VehicleState, mapper: GPMapper, budget: MissionBudget
    ) -> Optional[Waypoint]:
        if budget.remaining_m < self.cfg.min_leg_m:
            return None

        cand = self._draw_candidates()
        dist = np.linalg.norm(cand - state.position[None, :], axis=1)

        leg_ok = (dist >= self.cfg.min_leg_m) & (dist <= self.cfg.max_leg_m)
        if not leg_ok.any():  # relax: fall back to the nearest candidate
            leg_ok = np.zeros(len(cand), dtype=bool)
            leg_ok[int(np.argmin(dist))] = True

        mask = leg_ok & self._separation_ok(cand)
        if not mask.any():  # everything too close to old picks: ignore the rule
            mask = leg_ok

        idx = np.flatnonzero(mask)
        if mapper.n_samples < self.cfg.warmup_samples:
            scores = self._warmup_scores(cand[idx])
        else:
            scores = self._gp_scores(mapper, cand[idx], dist[idx])
        if self.cfg.weight_turn > 0.0:
            scores = scores - self.cfg.weight_turn * self._turn_penalty(state, cand[idx])

        best = cand[idx[int(np.argmax(scores))]]
        wp = Waypoint(float(best[0]), float(best[1]), float(best[2]))
        self._visited_xy.append(np.array([wp.x, wp.y], dtype=float))
        return wp

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _draw_candidates(self) -> np.ndarray:
        """(N, 3) random candidates in the survey box at survey altitude."""
        n = self.cfg.n_candidates
        xs = self._rng.uniform(self.survey.x_min, self.survey.x_max, size=n)
        ys = self._rng.uniform(self.survey.y_min, self.survey.y_max, size=n)
        zs = np.array(
            [float(self.seabed_fn(float(x), float(y))) for x, y in zip(xs, ys)]
        ) + self.survey.altitude_m
        return np.column_stack([xs, ys, zs])

    def _separation_ok(self, cand: np.ndarray) -> np.ndarray:
        """Boolean mask: candidate is horizontally clear of every previous pick."""
        if not self._visited_xy:
            return np.ones(len(cand), dtype=bool)
        visited = np.asarray(self._visited_xy)  # (M, 2)
        d = np.hypot(
            cand[:, 0:1] - visited[None, :, 0], cand[:, 1:2] - visited[None, :, 1]
        )
        return d.min(axis=1) >= self.cfg.min_separation_m

    def _warmup_scores(self, cand: np.ndarray) -> np.ndarray:
        """Exploration scores: distance from previous picks (random if none)."""
        if not self._visited_xy:
            return self._rng.random(len(cand))
        visited = np.asarray(self._visited_xy)
        d = np.hypot(
            cand[:, 0:1] - visited[None, :, 0], cand[:, 1:2] - visited[None, :, 1]
        )
        return d.min(axis=1)

    def _turn_penalty(self, state: VehicleState, cand: np.ndarray) -> np.ndarray:
        """Normalized heading change (0 = straight ahead, 1 = U-turn) toward
        each candidate, to reduce zig-zag when cfg.weight_turn > 0."""
        heading = np.arctan2(cand[:, 1] - state.y, cand[:, 0] - state.x)
        turn = np.abs(np.arctan2(np.sin(heading - state.yaw),
                                 np.cos(heading - state.yaw)))
        return turn / np.pi

    def _gp_scores(
        self, mapper: GPMapper, cand: np.ndarray, dist: np.ndarray
    ) -> np.ndarray:
        """Informative-sampling score from the GP posterior (one vector call)."""
        mean, std = mapper.predict(cand)
        max_std = float(std.max())
        std_norm = std / max_std if max_std > 0.0 else np.zeros_like(std)
        boundary = np.exp(
            -np.abs(mean - self.boundary_salinity_psu) / self.cfg.boundary_scale_psu
        )
        return (
            self.cfg.weight_std * std_norm
            + self.cfg.weight_boundary * boundary
            - self.cfg.weight_travel * dist / self.cfg.max_leg_m
        )

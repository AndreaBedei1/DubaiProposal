"""In-situ (single-mission) sonar localizer for the spawned outfall.

Unlike :class:`~brinewatch.perception.sonar_background_locator.SonarBackgroundLocator`,
which subtracts a *pre-installation* baseline pass over the same poses (and so
requires the structure to have been absent once), this locator works from a
**single** inspection pass with the structure already in place — the operational
case where no clean baseline exists.

It has no ground-truth access. Native seabed clutter is rejected by combining
four structure-aware priors, none of which is simulator truth:

1. **Chart prior** — an approximate outfall position (and, optionally, the
   pipeline bearing) from the design chart gates contacts to a plausible box /
   corridor.
2. **Multi-aspect persistence** — a real structure returns echoes from many
   vehicle headings; contacts are accumulated across the orbit and a consensus
   is only trusted once its supporting contacts span a range of aspects.
3. **Geometric consistency with the diffuser line** — the diffuser is an
   elongated segment, so the inlier contacts must be collinear. A RANSAC line
   fit finds the largest aspect-diverse collinear set and rejects off-line
   clutter (rocks, ripple scarps) that a plain point-cluster would keep.
4. **Robust clustering + uncertainty** — the centre is the robust centroid of
   the RANSAC inliers; a bootstrap over the inliers yields a covariance ellipse
   and a 1-sigma radius, so the estimate carries a stated uncertainty.

Ground truth is used only by the caller, AFTER the run, to score the error.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

import numpy as np

from ..sensors.sonar_types import SonarFrame
from .sonar_diffuser_detector import DetectorConfig, SonarDiffuserDetector


@dataclass
class InSituLocatorConfig:
    detector: DetectorConfig = field(
        default_factory=lambda: DetectorConfig(min_range_m=6.0, z_threshold=3.5,
                                               min_area_bins=8))
    # ---- chart prior (design chart, NOT ground truth) ----------------------
    prior_xy: Optional[Tuple[float, float]] = None
    prior_gate_m: float = 30.0            # reject contacts far from the prior point
    prior_axis_deg: Optional[float] = None  # approximate pipeline/diffuser bearing
    corridor_halfwidth_m: float = 18.0    # reject contacts outside the axis corridor
    # ---- contact quality gates --------------------------------------------
    min_strength: float = 0.0             # robust-z gate (0 => keep detector output)
    max_area_bins: int = 1500
    # ---- collinear (diffuser-line) fit ------------------------------------
    ransac_iters: int = 200
    line_inlier_m: float = 3.0            # perpendicular distance to be an inlier
    min_inliers: int = 6
    min_aspect_span_deg: float = 25.0     # inliers must span this many aspect deg
    diffuser_length_m: float = 19.6       # expected segment length (chart)
    axis_tol_deg: float = 30.0            # allowed refit around the chart axis
    # ---- uncertainty -------------------------------------------------------
    bootstrap: int = 200


@dataclass
class InSituLocalization:
    estimate: Optional[Tuple[float, float]]   # robust centre (x, y)
    axis_deg: Optional[float]                 # fitted diffuser orientation
    sigma_radius_m: float                     # 1-sigma isotropic position uncertainty
    cov_semi_axes_m: Tuple[float, float]      # 1-sigma ellipse semi-axes (major, minor)
    cov_orient_deg: float                     # ellipse major-axis orientation
    n_contacts: int                           # gated contacts accumulated
    n_inliers: int                            # collinear consensus set size
    aspect_span_deg: float                    # heading span of the inliers
    along_track_extent_m: float               # inlier spread along the fitted axis
    across_track_rms_m: float                 # inlier RMS off the fitted axis
    fallback: bool
    reason: str = ""


class InSituDiffuserLocator:
    """Single-mission sonar localizer (no pre-installation baseline)."""

    name = "sonar_insitu"

    def __init__(self, cfg: InSituLocatorConfig = InSituLocatorConfig(),
                 seed: int = 0):
        self.cfg = cfg
        self.detector = SonarDiffuserDetector(cfg.detector)
        self._rng = np.random.default_rng(seed)
        # (x, y, heading, strength)
        self._contacts: List[Tuple[float, float, float, float]] = []
        self.frames_seen = 0

    # ------------------------------------------------------------------ #
    def ingest(self, frame: SonarFrame) -> int:
        """Detect, world-project and gate the contacts in one live frame.
        Returns the number of contacts kept."""
        self.frames_seen += 1
        heading = frame.vehicle_rpy[2] + frame.extrinsics.yaw_offset_rad
        added = 0
        for c in self.detector.detect(frame):
            if c.strength < self.cfg.min_strength:
                continue
            if c.area_bins > self.cfg.max_area_bins:
                continue
            bearing = heading + float(frame.bearing_of_col(c.centroid_col))
            fx = frame.extrinsics.forward_offset_m
            x0 = frame.vehicle_xyz[0] + fx * math.cos(heading)
            y0 = frame.vehicle_xyz[1] + fx * math.sin(heading)
            ex = x0 + c.range_m * math.cos(bearing)
            ey = y0 + c.range_m * math.sin(bearing)
            if not self._chart_plausible(ex, ey):
                continue
            self._contacts.append((ex, ey, heading, float(c.strength)))
            added += 1
        return added

    def ingest_all(self, frames: Sequence[SonarFrame]) -> int:
        return sum(self.ingest(f) for f in frames)

    # ------------------------------------------------------------------ #
    def _chart_plausible(self, x: float, y: float) -> bool:
        cfg = self.cfg
        if cfg.prior_xy is not None:
            if math.hypot(x - cfg.prior_xy[0], y - cfg.prior_xy[1]) > cfg.prior_gate_m:
                return False
            if cfg.prior_axis_deg is not None:
                a = math.radians(cfg.prior_axis_deg)
                dx, dy = x - cfg.prior_xy[0], y - cfg.prior_xy[1]
                perp = abs(-math.sin(a) * dx + math.cos(a) * dy)
                if perp > cfg.corridor_halfwidth_m:
                    return False
        return True

    # ------------------------------------------------------------------ #
    def localize(self) -> InSituLocalization:
        n = len(self._contacts)
        empty_ell = (0.0, 0.0)
        if n < self.cfg.min_inliers:
            return InSituLocalization(None, None, 0.0, empty_ell, 0.0, n, 0,
                                      0.0, 0.0, 0.0, True,
                                      f"only {n} gated contacts (< {self.cfg.min_inliers})")
        pts = np.array([(c[0], c[1]) for c in self._contacts], dtype=float)
        head = np.array([c[2] for c in self._contacts], dtype=float)

        fit = self._fit(pts, head)
        if fit is None:
            return InSituLocalization(None, None, 0.0, empty_ell, 0.0, n, 0,
                                      0.0, 0.0, 0.0, True,
                                      "no aspect-diverse collinear consensus")
        inl, axis_deg, centre = fit
        core = pts[inl]
        core_head = head[inl]
        aspect = _aspect_span_deg(core_head)
        if aspect < self.cfg.min_aspect_span_deg:
            return InSituLocalization(None, None, 0.0, empty_ell, 0.0, n,
                                      int(inl.sum()), round(aspect, 1),
                                      0.0, 0.0, 0.0, True,
                                      f"aspect span {aspect:.0f} deg too narrow")

        _, along, across = _pca_axis(core, np.median(core, axis=0))
        smaj, smin, orient, sigr = self._bootstrap_uncertainty(core, axis_deg)
        return InSituLocalization(
            estimate=(float(centre[0]), float(centre[1])),
            axis_deg=round(float(axis_deg), 1),
            sigma_radius_m=round(float(sigr), 2),
            cov_semi_axes_m=(round(float(smaj), 2), round(float(smin), 2)),
            cov_orient_deg=round(float(orient), 1),
            n_contacts=n, n_inliers=int(inl.sum()),
            aspect_span_deg=round(float(aspect), 1),
            along_track_extent_m=round(float(along), 2),
            across_track_rms_m=round(float(across), 2),
            fallback=False)

    @property
    def consensus(self) -> Optional[Tuple[float, float]]:
        return self.localize().estimate

    # ------------------------------------------------------------------ #
    def _fit(self, pts: np.ndarray, head: np.ndarray):
        """Return (inlier_mask, axis_deg, centre_xy) or None.

        With a chart axis prior the diffuser line is constrained to the known
        pipeline bearing (refined within ``axis_tol_deg``) and the across-track
        offset is a 1-D robust mode — this rejects off-line clutter that a free
        line fit would otherwise chain into a spurious diagonal. Without an
        axis prior it falls back to aspect-diverse RANSAC. In both cases the
        centre is the along-track MIDPOINT of the inlier extent (the diffuser
        centre), not the density-weighted centroid."""
        if self.cfg.prior_axis_deg is not None and self.cfg.prior_xy is not None:
            return self._fit_axis_prior(pts, head)
        return self._fit_free(pts, head)

    def _fit_axis_prior(self, pts: np.ndarray, head: np.ndarray):
        origin = np.asarray(self.cfg.prior_xy, dtype=float)
        a = math.radians(self.cfg.prior_axis_deg)
        for _ in range(2):                     # fit, then refine orientation once
            nrm = np.array([-math.sin(a), math.cos(a)])
            perp = (pts - origin) @ nrm
            # choose the perpendicular band maximizing count x aspect coverage:
            # the diffuser is seen from every orbit heading, a clutter band is
            # not, so aspect diversity separates them even when counts are close.
            within = np.abs(perp[:, None] - perp[None, :]) <= self.cfg.line_inlier_m
            best_seed, best_score = -1, -1.0
            for s in range(len(pts)):
                band = within[s]
                if band.sum() < self.cfg.min_inliers:
                    continue
                score = band.sum() * min(_aspect_span_deg(head[band]), 120.0)
                if score > best_score:
                    best_score, best_seed = score, s
            if best_seed < 0:
                return None
            mask = within[best_seed]
            # refine the axis within tolerance from the current inliers
            ax, _, _ = _pca_axis(pts[mask], np.median(pts[mask], axis=0))
            da = ((ax - self.cfg.prior_axis_deg + 90) % 180) - 90
            a = math.radians(self.cfg.prior_axis_deg
                             + max(-self.cfg.axis_tol_deg,
                                   min(self.cfg.axis_tol_deg, da)))
        nrm = np.array([-math.sin(a), math.cos(a)])
        u = np.array([math.cos(a), math.sin(a)])
        perp = (pts - origin) @ nrm
        mask = np.abs(perp - np.median(perp[mask])) <= self.cfg.line_inlier_m
        if mask.sum() < self.cfg.min_inliers:
            return None
        s = (pts[mask] - origin) @ u
        s_mid = 0.5 * (np.percentile(s, 5) + np.percentile(s, 95))
        perp_c = float(np.median(perp[mask]))
        centre = origin + s_mid * u + perp_c * nrm
        return mask, math.degrees(a), centre

    def _fit_free(self, pts: np.ndarray, head: np.ndarray):
        n = len(pts)
        best_mask, best_score = None, -1.0
        thr = self.cfg.line_inlier_m
        for _ in range(self.cfg.ransac_iters):
            i, j = self._rng.choice(n, size=2, replace=False)
            d = pts[j] - pts[i]
            norm = math.hypot(d[0], d[1])
            if norm < 1e-6:
                continue
            nvec = np.array([-d[1], d[0]]) / norm
            mask = np.abs((pts - pts[i]) @ nvec) <= thr
            k = int(mask.sum())
            if k < self.cfg.min_inliers:
                continue
            score = k * min(_aspect_span_deg(head[mask]), 90.0)
            if score > best_score:
                best_score, best_mask = score, mask
        if best_mask is None:
            return None
        core = pts[best_mask]
        cen0 = np.median(core, axis=0)
        axis_deg, _, _ = _pca_axis(core, cen0)
        a = math.radians(axis_deg)
        u = np.array([math.cos(a), math.sin(a)])
        s = (core - cen0) @ u
        centre = cen0 + 0.5 * (np.percentile(s, 5) + np.percentile(s, 95)) * u
        return best_mask, axis_deg, centre

    def _bootstrap_uncertainty(self, core: np.ndarray, axis_deg: float
                               ) -> Tuple[float, float, float, float]:
        """1-sigma ellipse (major, minor, orient deg) + isotropic radius from a
        bootstrap over the inlier along-track midpoint / across-track median
        (the same estimator used for the point estimate)."""
        B = max(self.cfg.bootstrap, 0)
        m = len(core)
        if B == 0 or m < 3:
            return 0.0, 0.0, 0.0, 0.0
        a = math.radians(axis_deg)
        u = np.array([math.cos(a), math.sin(a)])
        nrm = np.array([-math.sin(a), math.cos(a)])
        c0 = np.median(core, axis=0)
        cen = np.empty((B, 2))
        for b in range(B):
            idx = self._rng.integers(0, m, size=m)
            r = core[idx]
            s = (r - c0) @ u
            p = (r - c0) @ nrm
            cen[b] = c0 + (0.5 * (np.percentile(s, 5) + np.percentile(s, 95))) * u \
                + float(np.median(p)) * nrm
        cov = np.cov(cen.T)
        w, V = np.linalg.eigh(cov)
        w = np.clip(w, 0.0, None)
        smaj, smin = math.sqrt(w[1]), math.sqrt(w[0])
        orient = math.degrees(math.atan2(V[1, 1], V[0, 1]))
        sigr = math.sqrt(smaj ** 2 + smin ** 2)
        return smaj, smin, orient, sigr


# --------------------------------------------------------------------------- #
def _aspect_span_deg(headings: np.ndarray) -> float:
    """Angular span (deg) covered by a set of headings, robust to wrap-around.

    Returns the width of the smallest arc containing all headings."""
    if len(headings) < 2:
        return 0.0
    a = np.sort(np.mod(headings, 2 * math.pi))
    gaps = np.diff(np.concatenate([a, [a[0] + 2 * math.pi]]))
    return math.degrees(2 * math.pi - gaps.max())


def _pca_axis(core: np.ndarray, centre: np.ndarray) -> Tuple[float, float, float]:
    """Principal axis orientation (deg), along-track extent and across-track RMS
    of the inlier cloud about ``centre``."""
    d = core - centre
    if len(core) < 2:
        return 0.0, 0.0, 0.0
    cov = np.cov(d.T)
    w, V = np.linalg.eigh(cov)
    major = V[:, 1]
    axis_deg = math.degrees(math.atan2(major[1], major[0]))
    if axis_deg < -90.0:
        axis_deg += 180.0
    elif axis_deg > 90.0:
        axis_deg -= 180.0
    along = d @ major
    minor = V[:, 0]
    across = d @ minor
    extent = float(along.max() - along.min()) if len(along) else 0.0
    across_rms = float(np.sqrt(np.mean(across ** 2))) if len(across) else 0.0
    return axis_deg, extent, across_rms

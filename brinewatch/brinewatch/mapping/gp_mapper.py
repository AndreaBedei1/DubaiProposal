"""Online Gaussian-process reconstruction of the salinity field.

Exact GP regression with a fixed anisotropic RBF kernel (horizontal vs
vertical length scales) and Gaussian noise. The prior mean is the ambient
salinity profile, so the GP actually regresses the *anomaly*; far from data
the prediction reverts to ambient with prior uncertainty — exactly the
behaviour wanted for an environmental field.

Hyperparameters are fixed from config (no marginal-likelihood optimization);
that keeps the mapper deterministic and cheap, and is listed as future work.
"""
from __future__ import annotations

from typing import Callable, Iterable, List, Optional, Tuple

import numpy as np
from scipy.linalg import cho_factor, cho_solve, solve_triangular
from scipy.spatial.distance import cdist

from ..utils.config import GPConfig
from ..utils.types import CTDSample


class GPMapper:
    def __init__(self, cfg: GPConfig, ambient_fn: Callable[[np.ndarray], np.ndarray], seed: int = 0):
        """``ambient_fn(z)`` returns the prior-mean salinity at height z (z up)."""
        self.cfg = cfg
        self.ambient_fn = ambient_fn
        self._rng = np.random.default_rng(seed)
        self._X: List[np.ndarray] = []  # raw sample positions (3,)
        self._y: List[float] = []  # salinity anomalies vs ambient
        self._dirty = True
        self._chol = None
        self._alpha: Optional[np.ndarray] = None
        self._Xtrain: Optional[np.ndarray] = None  # possibly subsampled, scaled

    # ------------------------------------------------------------------ #
    @property
    def n_samples(self) -> int:
        return len(self._y)

    def add_sample(self, sample: CTDSample) -> None:
        pos = np.array([sample.x, sample.y, sample.z], dtype=float)
        anomaly = sample.salinity_psu - float(self.ambient_fn(np.asarray(sample.z)))
        self._X.append(pos)
        self._y.append(anomaly)
        self._dirty = True

    def add_samples(self, samples: Iterable[CTDSample]) -> None:
        for s in samples:
            self.add_sample(s)

    # ------------------------------------------------------------------ #
    def _scale(self, pts: np.ndarray) -> np.ndarray:
        scales = np.array([self.cfg.length_xy_m, self.cfg.length_xy_m, self.cfg.length_z_m])
        return pts / scales

    def _refit(self) -> None:
        n = len(self._y)
        if n == 0:
            self._chol = None
            self._alpha = None
            self._Xtrain = None
            self._dirty = False
            return
        X = np.asarray(self._X, dtype=float)
        y = np.asarray(self._y, dtype=float)
        if n > self.cfg.max_train_points:
            idx = self._rng.choice(n, size=self.cfg.max_train_points, replace=False)
            idx.sort()
            X, y = X[idx], y[idx]
        Xs = self._scale(X)
        sf2 = self.cfg.signal_sigma_psu ** 2
        K = sf2 * np.exp(-0.5 * cdist(Xs, Xs, "sqeuclidean"))
        K[np.diag_indices_from(K)] += self.cfg.noise_sigma_psu ** 2 + self.cfg.jitter
        self._chol = cho_factor(K, lower=True)
        self._alpha = cho_solve(self._chol, y)
        self._Xtrain = Xs
        self._dirty = False

    # ------------------------------------------------------------------ #
    def predict(self, points: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Predict absolute salinity (mean, std) at an (N, 3) array of points."""
        pts = np.atleast_2d(np.asarray(points, dtype=float))
        ambient = np.asarray(self.ambient_fn(pts[:, 2]), dtype=float)
        sf = self.cfg.signal_sigma_psu
        if self._dirty:
            self._refit()
        if self._alpha is None:
            return ambient.copy(), np.full(len(pts), sf)

        mean = np.empty(len(pts))
        std = np.empty(len(pts))
        sf2 = sf ** 2
        L = self._chol[0]  # lower-triangular factor
        chunk = max(1, int(self.cfg.predict_chunk))
        for i in range(0, len(pts), chunk):
            Ps = self._scale(pts[i:i + chunk])
            Kstar = sf2 * np.exp(-0.5 * cdist(Ps, self._Xtrain, "sqeuclidean"))
            mean[i:i + chunk] = Kstar @ self._alpha
            V = solve_triangular(L, Kstar.T, lower=True)
            var = sf2 - np.sum(V * V, axis=0)
            std[i:i + chunk] = np.sqrt(np.clip(var, 0.0, None))
        return ambient + mean, std

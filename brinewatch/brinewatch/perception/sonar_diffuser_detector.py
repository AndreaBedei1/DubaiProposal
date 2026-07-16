"""Classical detector for compact structures in ImagingSonar frames.

Pipeline (deterministic, no learning, no ground-truth access):

1. sanitize (NaN/negative removal) and ``log1p`` compress;
2. per-range-row robust background: at grazing incidence the seabed fills
   most azimuth bins of a range row roughly uniformly, so the row median is
   a good background estimate, while a compact man-made target occupies few
   columns and survives subtraction;
3. robust z-score per row using the median absolute deviation (MAD);
4. threshold (CFAR-like: the statistic adapts per range row);
5. connected-component extraction (8-connectivity) and small-blob rejection;
6. component features: z-weighted centroid, area, mean strength;
7. convert centroid to (range, sensor-frame bearing) via the frame geometry.

The detector sees ONLY the sonar frame; the caller converts contacts to
world coordinates using the synchronized pose (see sonar_localizer.py).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np
from scipy import ndimage

from ..sensors.sonar_types import SonarFrame


@dataclass
class DetectorConfig:
    z_threshold: float = 4.5  # robust z-score for a bin to be a candidate
    min_area_bins: int = 12  # reject speckle blobs smaller than this
    max_contacts: int = 3  # strongest components kept per frame
    min_range_m: float = 2.0  # ignore self/near-field returns
    mad_floor: float = 1.0e-3  # numerical floor for the row MAD


@dataclass(frozen=True)
class SonarContact:
    """A detected compact high-return structure in one frame."""

    range_m: float
    bearing_rad: float  # sensor frame, +CCW from boresight
    strength: float  # mean robust z-score over the component
    area_bins: int
    centroid_row: float
    centroid_col: float


class SonarDiffuserDetector:
    def __init__(self, cfg: DetectorConfig = DetectorConfig()):
        self.cfg = cfg

    def zscore(self, frame: SonarFrame) -> np.ndarray:
        """Robust per-row z-score image (background-subtracted)."""
        img = np.nan_to_num(np.asarray(frame.image, dtype=np.float64), nan=0.0)
        img[img < 0] = 0.0
        x = np.log1p(img)
        med = np.median(x, axis=1, keepdims=True)
        mad = np.median(np.abs(x - med), axis=1, keepdims=True) * 1.4826
        return (x - med) / (mad + self.cfg.mad_floor)

    def detect(self, frame: SonarFrame) -> List[SonarContact]:
        z = self.zscore(frame)
        mask = z > self.cfg.z_threshold

        # Blank the near field (self returns / mounting artefacts)
        ranges = frame.range_of_row(np.arange(frame.n_range))
        mask[ranges < self.cfg.min_range_m, :] = False
        if not mask.any():
            return []

        labels, n = ndimage.label(mask, structure=np.ones((3, 3), dtype=int))
        contacts: List[SonarContact] = []
        for comp in range(1, n + 1):
            rows, cols = np.nonzero(labels == comp)
            area = rows.size
            if area < self.cfg.min_area_bins:
                continue
            w = z[rows, cols]
            w = np.clip(w, 0.0, None) + 1e-9
            r_c = float(np.average(rows, weights=w))
            c_c = float(np.average(cols, weights=w))
            contacts.append(SonarContact(
                range_m=float(frame.range_of_row(r_c)),
                bearing_rad=float(frame.bearing_of_col(c_c)),
                strength=float(w.mean()),
                area_bins=int(area),
                centroid_row=r_c,
                centroid_col=c_c,
            ))
        contacts.sort(key=lambda c: c.strength * np.sqrt(c.area_bins), reverse=True)
        return contacts[: self.cfg.max_contacts]

"""Offline tests for the sonar stack: types, recorder, detector, localizer.

The 'pier_sonar_present/absent' fixtures are REAL official-HoloOcean
ImagingSonar frames captured in PierHarbor (see tests/fixtures/, generated
from outputs/pierharbor_recon_*): the present frame aims at the stock pier
structure, the absent frame at open water. No simulator or GPU is needed
here — exactly the replay-based workflow the detector is developed with.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from brinewatch.perception.sonar_diffuser_detector import (
    DetectorConfig,
    SonarDiffuserDetector,
)
from brinewatch.perception.sonar_localizer import (
    SonarDiffuserLocator,
    SonarLocalizerConfig,
)
from brinewatch.sensors.sonar_recorder import SonarRecorder, SonarReplay
from brinewatch.sensors.sonar_types import SonarExtrinsics, SonarFrame
from brinewatch.utils.types import VehicleState

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> SonarFrame:
    return SonarReplay.load(FIXTURES / f"pier_sonar_{name}.npz")


def synthetic_frame(target_range: float, target_bearing_rad: float,
                    pose_xyz=(0.0, 0.0, -18.0), yaw: float = 0.0,
                    shape=(128, 128), blob: float = 0.5) -> SonarFrame:
    """Zero background + a bright blob at the given range/bearing."""
    img = np.zeros(shape, dtype=np.float32)
    n_r, n_a = shape
    rmin, rmax, fov = 1.0, 40.0, 120.0
    row = int((target_range - rmin) / (rmax - rmin) * n_r)
    col = int(n_a * (0.5 - math.degrees(target_bearing_rad) / fov))
    img[max(0, row - 3):row + 4, max(0, col - 3):col + 4] = blob
    return SonarFrame(
        t=0.0, image=img, range_min_m=rmin, range_max_m=rmax,
        azimuth_fov_deg=fov, elevation_fov_deg=20.0,
        vehicle_xyz=tuple(map(float, pose_xyz)), vehicle_rpy=(0.0, 0.0, yaw),
    )


# --------------------------------------------------------------------------- #
# Frame geometry
# --------------------------------------------------------------------------- #
class TestSonarFrame:
    def test_range_mapping(self):
        f = synthetic_frame(20.0, 0.0)
        assert float(f.range_of_row(0)) == pytest.approx(1.0 + 39.0 / 256, abs=0.2)
        assert float(f.range_of_row(f.n_range - 1)) == pytest.approx(40.0, abs=0.2)

    def test_bearing_convention_col0_is_positive(self):
        f = synthetic_frame(20.0, 0.0)
        assert float(f.bearing_of_col(0)) > 0  # +FOV/2 edge
        assert float(f.bearing_of_col(f.n_azimuth - 1)) < 0
        mid = float(f.bearing_of_col((f.n_azimuth - 1) / 2.0))
        assert abs(mid) < math.radians(1.0)

    def test_world_bearing_includes_yaw_and_extrinsics(self):
        f = SonarFrame(
            t=0.0, image=np.zeros((8, 8), dtype=np.float32),
            range_min_m=1, range_max_m=40, azimuth_fov_deg=120,
            elevation_fov_deg=20, vehicle_xyz=(0, 0, -10),
            vehicle_rpy=(0, 0, math.pi / 2),
            extrinsics=SonarExtrinsics(yaw_offset_rad=0.1),
        )
        centre = (f.n_azimuth - 1) / 2.0
        assert float(f.world_bearing(centre)) == pytest.approx(math.pi / 2 + 0.1, abs=0.02)


# --------------------------------------------------------------------------- #
# Recorder / replay
# --------------------------------------------------------------------------- #
class TestRecorder:
    def test_round_trip(self, tmp_path):
        frame = synthetic_frame(15.0, 0.2, pose_xyz=(3.0, -4.0, -12.0), yaw=1.1)
        with SonarRecorder(tmp_path / "rec", meta={"world": "test"}) as rec:
            rec.add(frame)
            rec.add(synthetic_frame(18.0, -0.1))
        replay = SonarReplay(tmp_path / "rec")
        assert len(replay) == 2
        back = next(iter(replay))
        np.testing.assert_array_equal(back.image, frame.image)
        assert back.vehicle_xyz == frame.vehicle_xyz
        assert back.vehicle_rpy[2] == pytest.approx(1.1)
        assert replay.meta["world"] == "test"


# --------------------------------------------------------------------------- #
# Detector
# --------------------------------------------------------------------------- #
class TestDetector:
    def test_detects_real_pier_structure(self):
        frame = load_fixture("present")
        contacts = SonarDiffuserDetector().detect(frame)
        assert contacts, "stock pier structure must be detected in the real frame"
        best = contacts[0]
        assert 20.0 <= best.range_m <= 40.0
        assert abs(math.degrees(best.bearing_rad)) <= 60.0

    def test_no_contacts_in_open_water(self):
        frame = load_fixture("absent")
        assert SonarDiffuserDetector().detect(frame) == []

    def test_synthetic_blob_centroid_accuracy(self):
        f = synthetic_frame(22.0, math.radians(-15.0))
        contacts = SonarDiffuserDetector().detect(f)
        assert len(contacts) == 1
        assert contacts[0].range_m == pytest.approx(22.0, abs=1.0)
        assert math.degrees(contacts[0].bearing_rad) == pytest.approx(-15.0, abs=2.0)

    def test_speckle_rejected_by_min_area(self):
        f = synthetic_frame(22.0, 0.0)
        f.image[100, 20] = 5.0  # single-bin speckle far from the blob
        contacts = SonarDiffuserDetector(DetectorConfig(min_area_bins=12)).detect(f)
        assert len(contacts) == 1  # only the extended blob survives

    def test_near_field_blanked(self):
        # Blob fully inside the blanked near field (min_range 5 m)
        f = synthetic_frame(3.0, 0.0)
        det = SonarDiffuserDetector(DetectorConfig(min_range_m=5.0))
        assert det.detect(f) == []


# --------------------------------------------------------------------------- #
# Localizer (no ground truth anywhere)
# --------------------------------------------------------------------------- #
class TestLocalizer:
    TARGET = (30.0, 10.0)  # world position implied by the synthetic frames

    def _frame_from_pose(self, px, py, yaw):
        rng = math.hypot(self.TARGET[0] - px, self.TARGET[1] - py)
        world_bearing = math.atan2(self.TARGET[1] - py, self.TARGET[0] - px)
        return synthetic_frame(rng, world_bearing - yaw, pose_xyz=(px, py, -18.0), yaw=yaw)

    def test_constructor_takes_no_ground_truth(self):
        loc = SonarDiffuserLocator()
        assert not hasattr(loc, "true_xy")

    def test_consensus_from_multiple_poses(self):
        loc = SonarDiffuserLocator(SonarLocalizerConfig(min_hits_for_consensus=2))
        poses = [(5.0, 0.0, 0.3), (10.0, -5.0, 0.8), (0.0, 8.0, 0.1), (12.0, 4.0, 0.4)]
        detections = []
        for px, py, yaw in poses:
            det = loc.update(self._frame_from_pose(px, py, yaw))
            if det is not None:
                detections.append(det)
        assert loc.consensus is not None
        cx, cy = loc.consensus
        assert math.hypot(cx - self.TARGET[0], cy - self.TARGET[1]) < 2.0
        assert detections, "consistent contacts must eventually emit detections"

    def test_first_hit_alone_emits_nothing(self):
        loc = SonarDiffuserLocator(SonarLocalizerConfig(min_hits_for_consensus=2))
        det = loc.update(self._frame_from_pose(5.0, 0.0, 0.3))
        assert det is None  # corroboration required

    def test_observe_interface(self):
        loc = SonarDiffuserLocator(SonarLocalizerConfig(
            min_hits_for_consensus=1, min_aspect_diff_deg=0.0))
        state = VehicleState(t=0.0, x=0, y=0, z=-18)
        assert loc.observe(state, None) is None
        assert loc.observe(state, {"sonar": None}) is None
        frame = self._frame_from_pose(0.0, 0.0, 0.0)
        det = loc.observe(state, {"sonar": frame})
        assert det is not None
        assert math.hypot(det.est_x - self.TARGET[0], det.est_y - self.TARGET[1]) < 2.0

"""Unit tests for the core modules: plume, GP mapper, kinematic backend,
sensors, config loading and geometry helpers."""
from __future__ import annotations

import dataclasses
import math
from pathlib import Path

import numpy as np
import pytest

from brinewatch.mapping.gp_mapper import GPMapper
from brinewatch.plume.model import BrinePlume
from brinewatch.sensors.ctd import VirtualCTD
from brinewatch.sensors.locator import DiffuserLocator
from brinewatch.simulation.kinematic import KinematicBackend
from brinewatch.utils.config import MissionConfig, load_config, save_config
from brinewatch.utils.geometry import (
    boustrophedon,
    expanding_square,
    path_length,
    wrap_angle,
)
from brinewatch.utils.types import CTDSample, VehicleState, Waypoint


@pytest.fixture()
def cfg() -> MissionConfig:
    return MissionConfig()


@pytest.fixture()
def plume(cfg) -> BrinePlume:
    return BrinePlume(cfg.environment, cfg.outfall, cfg.plume)


# --------------------------------------------------------------------------- #
# Plume model
# --------------------------------------------------------------------------- #
class TestPlume:
    def test_strong_anomaly_at_impact_zone(self, cfg, plume):
        bed = float(plume.seabed_z(-24, 0))
        assert float(plume.salinity_anomaly(-24, 0, bed + 0.5, 0)) > 3.0

    def test_ambient_far_from_outfall(self, plume):
        assert float(plume.salinity_anomaly(55, 55, -15, 0)) < 0.3
        assert float(plume.salinity_anomaly(-55, -50, -30, 0)) < 0.3

    def test_anomaly_decays_with_height_above_bed(self, plume):
        bed = float(plume.seabed_z(10, 0))
        a = [float(plume.salinity_anomaly(10, 0, bed + h, 0)) for h in (0.5, 3.0, 8.0)]
        assert a[0] > a[1] > a[2]

    def test_far_field_dilutes_downstream(self, plume):
        vals = []
        for x in (0.0, 20.0, 45.0):
            bed = float(plume.seabed_z(x, 0))
            vals.append(float(plume.salinity_anomaly(x, 0, bed + 0.5, 0)))
        assert vals[0] > vals[1] > vals[2]

    def test_salinity_never_exceeds_discharge(self, cfg, plume):
        rng = np.random.default_rng(0)
        xs = rng.uniform(-60, 60, 2000)
        ys = rng.uniform(-60, 60, 2000)
        zs = np.asarray(plume.seabed_z(xs, ys)) + rng.uniform(0, 10, 2000)
        s = np.asarray(plume.salinity(xs, ys, zs, 0.0))
        assert float(s.max()) <= cfg.outfall.discharge_salinity_psu + 1e-9

    def test_tide_shifts_field_along_current(self, cfg, plume):
        bed = float(plume.seabed_z(25, 0))
        quarter = cfg.environment.tide_period_s / 4.0
        s0 = float(plume.salinity_anomaly(25, 0, bed + 0.5, 0.0))
        s1 = float(plume.salinity_anomaly(25, 0, bed + 0.5, quarter))
        assert abs(s0 - s1) > 1e-3
        # At max tide shift the whole pattern moved downstream by the amplitude:
        shifted = float(plume.salinity_anomaly(
            25 + cfg.environment.tide_amplitude_m, 0, bed + 0.5, quarter))
        assert shifted == pytest.approx(
            float(plume.salinity_anomaly(25, 0, bed + 0.5, 0.0)), rel=0.15)

    def test_ambient_stratification(self, plume):
        assert float(plume.ambient_salinity(-30)) > float(plume.ambient_salinity(-5))

    def test_seabed_plane(self, cfg, plume):
        env = cfg.environment
        assert float(plume.seabed_z(10, -20)) == pytest.approx(
            env.seabed_z0 + env.seabed_slope_x * 10 + env.seabed_slope_y * -20)


# --------------------------------------------------------------------------- #
# GP mapper
# --------------------------------------------------------------------------- #
class TestGPMapper:
    def _samples(self, plume, n, seed=0, box=40.0):
        rng = np.random.default_rng(seed)
        xs = rng.uniform(-box, box, n)
        ys = rng.uniform(-box, box, n)
        zs = np.asarray(plume.seabed_z(xs, ys)) + 1.0
        sal = np.asarray(plume.salinity(xs, ys, zs, 0.0)) + rng.normal(0, 0.05, n)
        return [CTDSample(t=float(i), x=float(xs[i]), y=float(ys[i]), z=float(zs[i]),
                          salinity_psu=float(sal[i]), temperature_c=24.0,
                          depth_m=float(-zs[i])) for i in range(n)]

    def test_empty_mapper_returns_prior(self, cfg, plume):
        gp = GPMapper(cfg.gp, plume.ambient_salinity, seed=0)
        mean, std = gp.predict(np.array([[0.0, 0.0, -20.0]]))
        assert mean[0] == pytest.approx(float(plume.ambient_salinity(-20.0)))
        assert std[0] == pytest.approx(cfg.gp.signal_sigma_psu)

    def test_fit_reduces_error_near_data(self, cfg, plume):
        gp = GPMapper(cfg.gp, plume.ambient_salinity, seed=0)
        gp.add_samples(self._samples(plume, 400, seed=1))
        test = self._samples(plume, 60, seed=2)
        pts = np.array([[s.x, s.y, s.z] for s in test])
        truth = np.asarray(plume.salinity(pts[:, 0], pts[:, 1], pts[:, 2], 0.0))
        mean, std = gp.predict(pts)
        rmse = float(np.sqrt(np.mean((mean - truth) ** 2)))
        assert rmse < 0.6
        # Uncertainty is much lower near data than the prior
        assert float(std.mean()) < 0.5 * cfg.gp.signal_sigma_psu

    def test_max_train_subsampling_path(self, cfg, plume):
        small = dataclasses.replace(cfg.gp, max_train_points=150)
        gp = GPMapper(small, plume.ambient_salinity, seed=0)
        gp.add_samples(self._samples(plume, 1200, seed=3))
        mean, std = gp.predict(np.array([[0.0, 0.0, -33.0], [10.0, 5.0, -33.0]]))
        assert np.all(np.isfinite(mean)) and np.all(np.isfinite(std))

    def test_deterministic(self, cfg, plume):
        pts = np.array([[5.0, -3.0, -32.0]])
        out = []
        for _ in range(2):
            gp = GPMapper(cfg.gp, plume.ambient_salinity, seed=9)
            gp.add_samples(self._samples(plume, 100, seed=4))
            out.append(gp.predict(pts))
        assert out[0][0][0] == out[1][0][0]
        assert out[0][1][0] == out[1][1][0]


# --------------------------------------------------------------------------- #
# Kinematic backend
# --------------------------------------------------------------------------- #
class TestKinematic:
    def _backend(self, cfg, noise=0.0):
        bk = dataclasses.replace(cfg.backend)
        bk.kinematic = dataclasses.replace(cfg.backend.kinematic,
                                           position_noise_sigma_m=noise)
        return KinematicBackend(bk, cfg.environment, (0.0, 0.0, -20.0), seed=0)

    def test_reaches_waypoint(self, cfg):
        be = self._backend(cfg)
        st = be.reset()
        wp = Waypoint(15.0, -10.0, -25.0)
        steps = 0
        while st.distance_to(wp) > wp.tolerance and steps < 1000:
            st = be.step_toward(wp)
            steps += 1
        assert steps < 200

    def test_speed_limits(self, cfg):
        be = self._backend(cfg)
        st = be.reset()
        wp = Waypoint(50.0, 0.0, -35.0)
        max_h, max_v = 0.0, 0.0
        for _ in range(120):
            st = be.step_toward(wp)
            max_h = max(max_h, math.hypot(st.vx, st.vy))
            max_v = max(max_v, abs(st.vz))
        assert max_h <= cfg.backend.kinematic.max_speed_h_mps * 1.05
        assert max_v <= cfg.backend.kinematic.max_speed_v_mps * 1.05

    def test_reset_restores_start(self, cfg):
        be = self._backend(cfg)
        s0 = be.reset()
        for _ in range(50):
            be.step_toward(Waypoint(30.0, 30.0, -25.0))
        s1 = be.reset()
        assert (s1.x, s1.y, s1.z, s1.t) == (s0.x, s0.y, s0.z, 0.0)

    def test_altitude_is_height_above_seabed(self, cfg):
        be = self._backend(cfg)
        st = be.reset()
        bed = (cfg.environment.seabed_z0 + cfg.environment.seabed_slope_x * st.x
               + cfg.environment.seabed_slope_y * st.y)
        assert st.altitude == pytest.approx(st.z - bed, abs=1e-6)


# --------------------------------------------------------------------------- #
# Sensors
# --------------------------------------------------------------------------- #
class TestSensors:
    def test_ctd_rate_limiting(self, cfg, plume):
        ctd = VirtualCTD(cfg.ctd, plume, seed=0)
        got = 0
        for k in range(100):  # 100 states at 10 Hz -> 1 Hz CTD gives ~10 samples
            st = VehicleState(t=k * 0.1, x=0, y=0, z=-30)
            if ctd.maybe_sample(st) is not None:
                got += 1
        assert 9 <= got <= 11

    def test_ctd_noise_statistics(self, cfg, plume):
        ctd = VirtualCTD(cfg.ctd, plume, seed=1)
        st = VehicleState(t=0.0, x=50.0, y=50.0, z=-15.0)
        truth = float(plume.salinity(50, 50, -15, 0))
        vals = np.array([ctd.sample(st).salinity_psu for _ in range(500)])
        assert abs(float(vals.mean()) - truth) < 0.02
        assert 0.6 * cfg.ctd.salinity_sigma_psu < float(vals.std()) < 1.5 * cfg.ctd.salinity_sigma_psu

    def test_locator_range_gate(self, cfg, plume):
        loc = DiffuserLocator(cfg.locator, plume.outfall_xy(), seed=2)
        far = VehicleState(t=0, x=plume.outfall_xy()[0] + 200, y=0, z=-30)
        assert all(loc.ping(far) is None for _ in range(50))
        near = VehicleState(t=0, x=plume.outfall_xy()[0] + 5, y=0, z=-30)
        hits = sum(loc.ping(near) is not None for _ in range(200))
        assert 140 <= hits <= 200  # detect_prob 0.9

    def test_locator_estimate_accuracy(self, cfg, plume):
        loc = DiffuserLocator(cfg.locator, plume.outfall_xy(), seed=3)
        near = VehicleState(t=0, x=plume.outfall_xy()[0] + 10, y=5, z=-30)
        est = np.array([(d.est_x, d.est_y) for d in
                        (loc.ping(near) for _ in range(300)) if d is not None])
        err = np.hypot(est[:, 0] - plume.outfall_xy()[0], est[:, 1] - plume.outfall_xy()[1])
        assert float(err.mean()) < 3.0


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
class TestConfig:
    def test_defaults(self):
        cfg = load_config(None)
        assert cfg.backend.name == "kinematic"
        assert cfg.budget.max_distance_m > 0

    def test_yaml_roundtrip(self, tmp_path):
        cfg = MissionConfig(seed=99)
        path = tmp_path / "cfg.yaml"
        save_config(cfg, path)
        loaded = load_config(path)
        assert loaded == cfg

    def test_unknown_key_raises(self, tmp_path):
        path = tmp_path / "bad.yaml"
        path.write_text("outfall:\n  not_a_key: 1\n", encoding="utf-8")
        with pytest.raises(KeyError):
            load_config(path)

    def test_overrides_deep_merge(self):
        cfg = load_config(None, overrides={"budget": {"max_distance_m": 123.0}})
        assert cfg.budget.max_distance_m == 123.0
        assert cfg.budget.locate_fraction == MissionConfig().budget.locate_fraction


# --------------------------------------------------------------------------- #
# Geometry
# --------------------------------------------------------------------------- #
class TestGeometry:
    def test_boustrophedon_bounds_and_alternation(self):
        pts = boustrophedon(-10, 10, -10, 10, spacing=5.0)
        arr = np.array(pts)
        assert arr[:, 0].min() == -10 and arr[:, 0].max() == 10
        assert arr[:, 1].min() == -10 and arr[:, 1].max() == 10
        # Alternation: consecutive line starts alternate x sides
        assert pts[0][0] == -10 and pts[1][0] == 10 and pts[2][0] == 10 and pts[3][0] == -10

    def test_path_length_square(self):
        square = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
        assert path_length(square) == pytest.approx(40.0)

    def test_expanding_square_grows(self):
        pts = list(expanding_square((0.0, 0.0), step=10.0, n_legs=8))
        d = [math.hypot(x, y) for x, y in pts]
        assert max(d) > 20.0

    def test_wrap_angle(self):
        # +-pi is the same heading; floating point sign at the branch cut is fine
        assert abs(wrap_angle(3 * math.pi)) == pytest.approx(math.pi)
        assert abs(wrap_angle(-3 * math.pi)) == pytest.approx(math.pi)
        assert wrap_angle(0.5) == pytest.approx(0.5)
        assert wrap_angle(2 * math.pi + 0.3) == pytest.approx(0.3)


class TestApplicationConfigs:
    """The application-facing YAML configs must load and satisfy the
    invariants the PFH demo relies on."""

    REPO = Path(__file__).resolve().parents[1]

    def test_pfh2026_config_valid(self):
        cfg = load_config(self.REPO / "configs" / "pfh2026_holoocean.yaml")
        assert cfg.locator.mode == "sonar"
        assert cfg.backend.holoocean.sonar_enabled
        assert cfg.backend.holoocean.defer_scene_build
        assert cfg.locator.prior_x is not None and cfg.locator.prior_y is not None
        # chart prior must be inside the survey box
        assert cfg.survey.x_min <= cfg.locator.prior_x <= cfg.survey.x_max
        assert cfg.survey.y_min <= cfg.locator.prior_y <= cfg.survey.y_max
        # survey never above the safety ceiling
        assert cfg.survey.max_z_m < -1.0

    def test_benchmark_configs_valid(self):
        static = load_config(self.REPO / "configs" / "benchmark_static.yaml")
        dynamic = load_config(self.REPO / "configs" / "benchmark_dynamic.yaml")
        assert static.environment.tide_amplitude_m == 0.0
        assert dynamic.environment.tide_amplitude_m > 0.0
        assert static.backend.name == "kinematic"


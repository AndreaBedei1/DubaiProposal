"""Typed configuration schema for BrineWatch, loaded from YAML.

Every module reads its parameters from these dataclasses; nothing is
hard-coded. Unknown YAML keys raise, so typos fail loudly.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, TypeVar, Union

import yaml

T = TypeVar("T")


# --------------------------------------------------------------------------- #
# Environment / scenario
# --------------------------------------------------------------------------- #
@dataclass
class EnvironmentConfig:
    """Ambient water column and seabed. The seabed is a plane
    z = seabed_z0 + slope_x * x + slope_y * y (analytic; the HoloOcean terrain
    is close but not identical — see docs/assumptions.md)."""

    ambient_salinity_psu: float = 39.5  # Gulf-like ambient
    salinity_stratification_per_m: float = 0.005  # PSU per metre of depth
    ambient_temperature_c: float = 24.0
    temperature_gradient_per_m: float = -0.01  # cooler with depth
    seabed_z0: float = -34.0
    seabed_slope_x: float = -0.015
    seabed_slope_y: float = 0.0
    current_dir_deg: float = 0.0  # direction the current flows TOWARD (0 = +x)
    # Tidal excursion of the plume pattern. Kept small by default: one mission
    # (~2000 s) spans most of a tide period, and a large excursion makes the
    # static-field reconstruction target ambiguous (documented challenge).
    tide_amplitude_m: float = 2.5
    tide_period_s: float = 2400.0


@dataclass
class OutfallConfig:
    """Desalination outfall geometry (diffuser on the seabed)."""

    x: float = -30.0
    y: float = 0.0
    axis_deg: float = 90.0  # diffuser axis orientation (ports spread along it)
    n_ports: int = 4
    port_spacing_m: float = 3.0
    riser_height_m: float = 1.0
    discharge_salinity_psu: float = 68.0
    discharge_temperature_c: float = 27.5


@dataclass
class PlumeConfig:
    """Analytic brine plume shape parameters (NOT CFD — see docs/assumptions.md).

    Near field: dense jet rises ~rise_height above the port then collapses,
    impacting the seabed ~nearfield_offset downstream. Far field: a bottom
    gravity current spreading downstream, widening and diluting with distance.
    """

    rise_height_m: float = 4.0
    nearfield_offset_m: float = 6.0
    nearfield_sigma_xy_m: float = 4.0
    nearfield_sigma_z_m: float = 1.5
    nearfield_peak_anomaly_psu: float = 12.0
    farfield_peak_anomaly_psu: float = 8.0
    farfield_initial_width_m: float = 6.0
    farfield_spread_rate: float = 0.18  # width growth per metre downstream
    layer_thickness_m: float = 1.6  # e-folding height of the bottom layer
    dilution_length_m: float = 35.0  # distance at which far-field amplitude halves
    upstream_tail_m: float = 4.0  # small upstream smearing of the impact zone
    temperature_anomaly_ratio: float = 0.25  # dT (degC) per PSU of salinity anomaly


# --------------------------------------------------------------------------- #
# Sensors
# --------------------------------------------------------------------------- #
@dataclass
class CTDConfig:
    rate_hz: float = 1.0  # samples per simulated second
    salinity_sigma_psu: float = 0.05
    temperature_sigma_c: float = 0.02
    depth_sigma_m: float = 0.10


@dataclass
class LocatorConfig:
    """Sonar-like diffuser locator (simulated detection model, see docs)."""

    max_range_m: float = 25.0
    detect_prob: float = 0.9  # per ping, when in range
    range_sigma_m: float = 0.4
    bearing_sigma_deg: float = 4.0
    prior_sigma_m: float = 12.0  # error injected on the a-priori outfall position
    n_confirm: int = 3  # detections averaged before declaring the outfall found


# --------------------------------------------------------------------------- #
# Mission / survey
# --------------------------------------------------------------------------- #
@dataclass
class SurveyConfig:
    x_min: float = -60.0
    x_max: float = 60.0
    y_min: float = -60.0
    y_max: float = 60.0
    altitude_m: float = 2.0  # survey altitude above the (analytic) seabed
    grid_resolution_m: float = 3.0  # evaluation grid resolution


@dataclass
class BudgetConfig:
    max_distance_m: float = 1600.0
    checkpoints: List[float] = field(default_factory=lambda: [0.25, 0.5, 0.75, 1.0])
    locate_fraction: float = 0.25  # max budget fraction spent searching the outfall


@dataclass
class LawnmowerConfig:
    line_spacing_m: float = 10.0
    along_x: bool = True


@dataclass
class AdaptiveConfig:
    n_candidates: int = 250
    weight_std: float = 0.7
    weight_boundary: float = 1.2
    weight_travel: float = 0.25
    # Penalty on heading change toward a candidate (0..1 of a U-turn).
    # 0 disables it (benchmark default); set >0 for smoother, more watchable
    # live missions with less yaw thrash.
    weight_turn: float = 0.0
    boundary_scale_psu: float = 0.6  # how sharply "near the threshold" is rewarded
    min_leg_m: float = 8.0
    max_leg_m: float = 45.0
    min_separation_m: float = 4.0  # candidates closer than this to old samples are skipped
    warmup_samples: int = 25  # before this many samples, fall back to baseline coverage


@dataclass
class GPConfig:
    length_xy_m: float = 12.0
    length_z_m: float = 1.8
    signal_sigma_psu: float = 2.5
    noise_sigma_psu: float = 0.08
    max_train_points: int = 800
    jitter: float = 1.0e-6
    predict_chunk: int = 4000


@dataclass
class ComplianceConfig:
    """Mixing-zone rule: beyond mixing_zone_radius_m from the outfall, the
    near-bottom salinity must not exceed ambient * (1 + threshold_increment_pct/100).

    NOTE: radius scaled down (real permits: 100-300 m) so the scenario fits the
    140 m SimpleUnderwater world; fully configurable."""

    mixing_zone_radius_m: float = 40.0
    threshold_increment_pct: float = 5.0
    eval_altitude_m: float = 1.0  # metres above seabed for the evaluation layer


# --------------------------------------------------------------------------- #
# Backends
# --------------------------------------------------------------------------- #
@dataclass
class KinematicConfig:
    max_speed_h_mps: float = 0.9
    max_speed_v_mps: float = 0.4
    accel_tau_s: float = 1.5  # first-order response time constant
    position_noise_sigma_m: float = 0.05


@dataclass
class HoloOceanConfig:
    package_name: str = "Ocean"
    world: str = "SimpleUnderwater"
    ticks_per_sec: int = 30
    control_ticks: int = 15  # sim ticks per control period (15 @ 30 tps = 0.5 s)
    frames_per_sec: bool = False  # False = run as fast as possible
    show_viewport: bool = True
    window_width: int = 1024
    window_height: int = 576
    spawn_outfall_props: bool = True
    draw_debug: bool = True  # draw waypoints/detections in the viewport
    min_altitude_m: float = 1.0  # safety floor when commanding depth


@dataclass
class BackendConfig:
    name: str = "kinematic"  # "kinematic" | "holoocean"
    dt_control_s: float = 0.5  # control period used by the kinematic backend
    kinematic: KinematicConfig = field(default_factory=KinematicConfig)
    holoocean: HoloOceanConfig = field(default_factory=HoloOceanConfig)


# --------------------------------------------------------------------------- #
# Root
# --------------------------------------------------------------------------- #
@dataclass
class MissionConfig:
    name: str = "brinewatch_mission"
    seed: int = 7
    planner: str = "adaptive"  # "lawnmower" | "adaptive"
    environment: EnvironmentConfig = field(default_factory=EnvironmentConfig)
    outfall: OutfallConfig = field(default_factory=OutfallConfig)
    plume: PlumeConfig = field(default_factory=PlumeConfig)
    ctd: CTDConfig = field(default_factory=CTDConfig)
    locator: LocatorConfig = field(default_factory=LocatorConfig)
    survey: SurveyConfig = field(default_factory=SurveyConfig)
    budget: BudgetConfig = field(default_factory=BudgetConfig)
    lawnmower: LawnmowerConfig = field(default_factory=LawnmowerConfig)
    adaptive: AdaptiveConfig = field(default_factory=AdaptiveConfig)
    gp: GPConfig = field(default_factory=GPConfig)
    compliance: ComplianceConfig = field(default_factory=ComplianceConfig)
    backend: BackendConfig = field(default_factory=BackendConfig)


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def _from_dict(cls: Type[T], data: Dict[str, Any], path: str = "") -> T:
    """Recursively build a dataclass from a nested dict, failing on unknown keys."""
    if data is None:
        return cls()
    if not isinstance(data, dict):
        raise TypeError(f"Expected mapping for {cls.__name__} at '{path}', got {type(data).__name__}")
    field_map = {f.name: f for f in dataclasses.fields(cls)}
    unknown = set(data) - set(field_map)
    if unknown:
        raise KeyError(f"Unknown config key(s) {sorted(unknown)} at '{path or cls.__name__}'")
    kwargs: Dict[str, Any] = {}
    for key, value in data.items():
        f = field_map[key]
        ftype = f.type if isinstance(f.type, type) else _resolve_type(cls, f.name)
        if dataclasses.is_dataclass(ftype):
            kwargs[key] = _from_dict(ftype, value, f"{path}.{key}" if path else key)
        else:
            kwargs[key] = value
    return cls(**kwargs)


def _resolve_type(cls: Type, field_name: str) -> Any:
    """Resolve possibly-string annotations (from __future__ annotations)."""
    import typing

    hints = typing.get_type_hints(cls)
    return hints.get(field_name, Any)


def load_config(path: Union[str, Path, None] = None, overrides: Optional[Dict[str, Any]] = None) -> MissionConfig:
    """Load a MissionConfig from YAML; missing sections use defaults.

    ``overrides`` is a nested dict merged on top of the file contents.
    """
    data: Dict[str, Any] = {}
    if path is not None:
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    if overrides:
        data = _deep_merge(data, overrides)
    return _from_dict(MissionConfig, data)


def _deep_merge(base: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def config_to_dict(cfg: MissionConfig) -> Dict[str, Any]:
    return dataclasses.asdict(cfg)


def save_config(cfg: MissionConfig, path: Union[str, Path]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(config_to_dict(cfg), fh, sort_keys=False)

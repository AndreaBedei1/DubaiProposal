"""Cross-adapter geometry parity regression test.

The SAME OutfallSceneBuilder geometry is spawned through two backends with
different rotation encodings:

- official ``spawn_prop``: rotation triple is a DIRECTION VECTOR
  (UE ``Conv_VectorToRotator``, prop local +X aligned to it)
- fork ``SpawnAsset``: true ``[roll, pitch, yaw]`` (C++ ``RPYToRotator``)

This test builds the identical scene with both adapters against mock
environments and asserts, component by component, that the decoded
world-space long axes, positions and scales match. It guards against any
future change that would let the visual and acoustic structures diverge.
"""
import math

import numpy as np
import pytest

from brinewatch.simulation.custom_engine import make_asset_spawner
from brinewatch.simulation.outfall_scene import (
    OutfallSceneBuilder,
    OutfallSceneConfig,
)
from brinewatch.utils.config import OutfallConfig
from brinewatch.utils.terrain import TerrainMap


# ---- forward models of the two engine-side rotation decoders --------------- #
def axis_from_direction(d):
    """Conv_VectorToRotator on a Z-up prop: long axis after the rotator."""
    a, b, c = d
    n = math.sqrt(a * a + b * b + c * c)
    if n < 1e-12:
        return np.array([0.0, 0.0, 1.0])
    w = math.atan2(b, a)
    p = math.atan2(c, math.hypot(a, b))
    return np.array([-math.cos(w) * math.sin(p),
                     -math.sin(w) * math.sin(p), math.cos(p)])


def axis_from_rpy(rpy):
    """RPYToRotator on a Z-up mesh: axis = Rz(yaw) Ry(pitch) z."""
    _, p, w = (math.radians(v) for v in rpy)
    return np.array([math.sin(p) * math.cos(w),
                     math.sin(p) * math.sin(w), math.cos(p)])


# ---- mock spawn backends ---------------------------------------------------- #
class PropEnv:
    def __init__(self):
        self.calls = []

    def spawn_prop(self, prop_type, location=None, rotation=None, scale=None,
                   sim_physics=False, material=""):
        self.calls.append({"type": prop_type, "loc": list(location),
                           "rot": list(rotation), "scale": list(scale)})


class _FakeCommand:
    def __init__(self):
        self.type = None
        self.numbers = []
        self.strings = []

    def set_command_type(self, t):
        self.type = t

    def add_number_parameters(self, params):
        self.numbers.append(list(params))

    def add_string_parameters(self, s):
        self.strings.append(s)


class _FakeHoloocean:
    class command:  # noqa: N801
        Command = _FakeCommand


class AssetEnv:
    def __init__(self):
        self.calls = []

    def _enqueue_command(self, cmd):
        self.calls.append({"mesh": cmd.strings[0], "loc": cmd.numbers[0],
                           "rpy": cmd.numbers[1], "scale": cmd.numbers[2]})


# ---- the parity test -------------------------------------------------------- #
def build_scene(spawn_env, spawn_fn=None):
    xs = np.linspace(-60, 60, 13)
    ys = np.linspace(-60, 60, 13)
    terrain = TerrainMap(xs, ys, np.full((13, 13), -50.0))
    builder = OutfallSceneBuilder(
        env=spawn_env, agent_name="t",
        outfall=OutfallConfig(x=0.0, y=0.0, axis_deg=30.0, n_ports=6,
                              port_spacing_m=3.2),
        scene=OutfallSceneConfig(structure_yaw_deg=30.0, scatter_rocks=4,
                                 berm_seed=7),
        terrain=terrain, spawn_fn=spawn_fn, log=lambda *_: None)
    builder.build()
    return builder


def test_adapters_produce_identical_world_geometry():
    prop_env = PropEnv()
    build_scene(prop_env)

    asset_env = AssetEnv()
    spawn = make_asset_spawner(asset_env, _FakeHoloocean)
    build_scene(asset_env, spawn_fn=spawn)

    assert len(prop_env.calls) == len(asset_env.calls) > 60

    mesh_of = {"cylinder": "Cylinder", "box": "Cube", "sphere": "Sphere",
               "cone": "Cone"}
    for k, (p, a) in enumerate(zip(prop_env.calls, asset_env.calls)):
        # same primitive
        assert mesh_of[p["type"]] in a["mesh"], f"component {k}"
        # same world location and scale
        np.testing.assert_allclose(p["loc"], a["loc"], atol=1e-6,
                                   err_msg=f"component {k} location")
        np.testing.assert_allclose(p["scale"], a["scale"], atol=1e-6,
                                   err_msg=f"component {k} scale")
        # same world long axis (sign-free: cylinders/boxes are symmetric)
        ax_p = axis_from_direction(p["rot"])
        ax_a = axis_from_rpy(a["rpy"])
        cos = abs(float(np.dot(ax_p, ax_a)))
        assert cos > math.cos(math.radians(0.6)), (
            f"component {k} ({p['type']}): axes diverge "
            f"(prop {ax_p}, asset {ax_a})")


def test_adapter_parity_covers_all_component_kinds():
    prop_env = PropEnv()
    builder = build_scene(prop_env)
    kinds = {c.kind.split("_")[0] for c in builder.components}
    # the scene exercises every rotation regime: sloped pipes, collars,
    # vertical risers, tilted nozzles, boxes (sleepers), ellipsoid rocks
    for expected in ("approach", "riser", "nozzle", "sleeper", "berm",
                     "end", "transition", "gravel"):
        assert any(k.startswith(expected) for k in kinds) or any(
            c.kind.startswith(expected) for c in builder.components), expected

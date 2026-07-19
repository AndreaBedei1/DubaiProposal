"""Tests for the custom-engine integration and the rotation conventions.

No engine required: geometry maths + failure modes + spawn-call recording.
"""
import math
import os
from unittest import mock

import numpy as np
import pytest

from brinewatch.simulation.custom_engine import (
    ENV_VAR,
    CustomEngineError,
    PROP_MESHES,
    direction_to_rpy,
    discover_custom_engine,
    editor_launch_args,
    make_asset_spawner,
    repo_root,
    resolve_custom_engine,
)
from brinewatch.simulation.outfall_scene import prop_rotation_for_axis

# The custom engine (Unreal project) is gitignored and only present on a dev
# machine that has it checked out at <repo>/engine; CI runs without it.
_HAS_IN_PROJECT_ENGINE = (repo_root() / "engine" / "Holodeck.uproject").is_file()


# --------------------------------------------------------------------------- #
# prop_rotation_for_axis: the official-engine direction-vector encoding
# --------------------------------------------------------------------------- #
def _axis_from_direction(d):
    """Forward model of the engine's Conv_VectorToRotator on a Z-up prop."""
    a, b, c = d
    n = math.sqrt(a * a + b * b + c * c)
    if n < 1e-12:
        return (0.0, 0.0, 1.0)
    w = math.atan2(b, a)
    p = math.atan2(c, math.hypot(a, b))
    return (-math.cos(w) * math.sin(p), -math.sin(w) * math.sin(p), math.cos(p))


@pytest.mark.parametrize("axis", [
    (0.0, 0.0, 1.0),           # vertical riser
    (1.0, 0.0, 0.0),           # horizontal along +x
    (0.0, 1.0, 0.0),           # horizontal along +y
    (0.7, 0.7, 0.0),           # horizontal diagonal
    (0.9, 0.1, 0.15),          # graded pipe
    (0.4, -0.5, 0.76),         # nozzle-like
])
def test_prop_rotation_round_trip(axis):
    d = prop_rotation_for_axis(*axis)
    got = _axis_from_direction(d)
    want = np.asarray(axis, dtype=float)
    want /= np.linalg.norm(want)
    got = np.asarray(got, dtype=float)
    # long axis has no sign; compare up to sign, tolerate the 0.3 deg cap
    cos = abs(float(np.dot(got, want)))
    assert cos > math.cos(math.radians(0.5)), (axis, d, got)


def test_prop_rotation_vertical_is_zero_vector():
    assert prop_rotation_for_axis(0.0, 0.0, 1.0) == [0.0, 0.0, 0.0]
    assert prop_rotation_for_axis(0.0, 0.0, -2.5) == [0.0, 0.0, 0.0]


def test_prop_rotation_horizontal_keeps_heading():
    # exactly horizontal must NOT degenerate to atan2(0,0)
    d = prop_rotation_for_axis(math.cos(0.7), math.sin(0.7), 0.0)
    assert abs(d[2]) > 0.0  # tau capped below 90 -> nonzero z component
    got = _axis_from_direction(d)
    heading = math.atan2(got[1], got[0]) % math.pi
    assert abs(heading - 0.7) < math.radians(0.5)


# --------------------------------------------------------------------------- #
# direction_to_rpy: SpawnAsset (fork) encoding from the same internal triple
# --------------------------------------------------------------------------- #
def _axis_from_rpy(rpy):
    """Forward model of RPYToRotator on a Z-up mesh: axis = Rz(yaw)Ry(pitch)z."""
    _, p, w = (math.radians(v) for v in rpy)
    return (math.sin(p) * math.cos(w), math.sin(p) * math.sin(w), math.cos(p))


@pytest.mark.parametrize("axis", [
    (0.0, 0.0, 1.0),
    (1.0, 0.0, 0.0),
    (0.7, 0.7, 0.0),
    (0.9, 0.1, 0.15),
    (0.4, -0.5, 0.76),
])
def test_direction_to_rpy_matches_axis(axis):
    d = prop_rotation_for_axis(*axis)
    rpy = direction_to_rpy(d)
    got = np.asarray(_axis_from_rpy(rpy), dtype=float)
    want = np.asarray(axis, dtype=float)
    want /= np.linalg.norm(want)
    cos = abs(float(np.dot(got, want)))
    assert cos > math.cos(math.radians(0.5)), (axis, d, rpy, got)


def test_direction_to_rpy_zero_vector_is_identity():
    assert direction_to_rpy([0.0, 0.0, 0.0]) == [0.0, 0.0, 0.0]


# --------------------------------------------------------------------------- #
# resolve_custom_engine failure modes (loud, actionable)
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(not _HAS_IN_PROJECT_ENGINE,
                    reason="in-project engine not checked out")
def test_discover_finds_in_project_engine(monkeypatch):
    # no env var -> auto-discovery finds <repo>/engine/Holodeck.uproject
    monkeypatch.delenv(ENV_VAR, raising=False)
    eng = discover_custom_engine()
    assert eng.uproject.name == "Holodeck.uproject"
    assert eng.uproject.is_file()
    assert eng.octrees_dir.name == "Octrees"


def test_env_var_override_engine_dir(tmp_path, monkeypatch):
    # env var pointing directly at an engine dir wins
    (tmp_path / "Holodeck.uproject").write_text("{}")
    monkeypatch.setenv(ENV_VAR, str(tmp_path))
    eng = discover_custom_engine(level="TestWorld")
    assert eng.root == tmp_path
    assert eng.level == "TestWorld"
    assert eng.uproject.name == "Holodeck.uproject"


def test_env_var_override_fork_root(tmp_path, monkeypatch):
    # env var pointing at a fork root (engine/ + client/) is also accepted
    (tmp_path / "engine").mkdir()
    (tmp_path / "engine" / "Holodeck.uproject").write_text("{}")
    (tmp_path / "client" / "src" / "holoocean").mkdir(parents=True)
    (tmp_path / "client" / "src" / "holoocean" / "__init__.py").write_text("")
    monkeypatch.setenv(ENV_VAR, str(tmp_path))
    eng = discover_custom_engine()
    assert eng.uproject == tmp_path / "engine" / "Holodeck.uproject"
    assert eng.client_src == tmp_path / "client" / "src"


def test_discovery_without_engine_raises(tmp_path, monkeypatch):
    # env var at a dir with no uproject; falls through to the in-project
    # engine if present, else raises a clear error
    monkeypatch.setenv(ENV_VAR, str(tmp_path))
    if _HAS_IN_PROJECT_ENGINE:
        assert discover_custom_engine().uproject.is_file()
    else:
        with pytest.raises(CustomEngineError, match="not found"):
            discover_custom_engine()


def test_editor_launch_args_include_env_bounds(tmp_path, monkeypatch):
    (tmp_path / "client" / "src" / "holoocean").mkdir(parents=True)
    (tmp_path / "client" / "src" / "holoocean" / "__init__.py").write_text("")
    (tmp_path / "engine").mkdir()
    (tmp_path / "engine" / "Holodeck.uproject").write_text("{}")
    monkeypatch.setenv(ENV_VAR, str(tmp_path))
    fake_editor = tmp_path / "UnrealEditor.exe"
    fake_editor.write_text("")
    eng = resolve_custom_engine()
    args = editor_launch_args(eng, editor_exe=str(fake_editor),
                              octree_min_m=0.05, env_min=(-50, -60, -70),
                              env_max=(50, 60, 5))
    joined = " ".join(args)
    assert "-OctreeMin=0.05" in joined
    assert "-EnvMinZ=-70" in joined and "-EnvMaxY=60" in joined
    assert "-game" in args


def test_editor_launch_args_require_editor(tmp_path, monkeypatch):
    (tmp_path / "client" / "src" / "holoocean").mkdir(parents=True)
    (tmp_path / "client" / "src" / "holoocean" / "__init__.py").write_text("")
    (tmp_path / "engine").mkdir()
    (tmp_path / "engine" / "Holodeck.uproject").write_text("{}")
    monkeypatch.setenv(ENV_VAR, str(tmp_path))
    monkeypatch.delenv("UNREAL_EDITOR_EXE", raising=False)
    with pytest.raises(CustomEngineError, match="editor executable"):
        editor_launch_args(resolve_custom_engine())


# --------------------------------------------------------------------------- #
# make_asset_spawner: spawn_prop-compatible signature -> SpawnAsset commands
# --------------------------------------------------------------------------- #
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
    class command:  # noqa: N801 - mimics module layout
        Command = _FakeCommand


class _FakeEnv:
    def __init__(self):
        self.enqueued = []

    def _enqueue_command(self, cmd):
        self.enqueued.append(cmd)


def test_asset_spawner_maps_props_to_meshes():
    env = _FakeEnv()
    spawn = make_asset_spawner(env, _FakeHoloocean)
    spawn("cylinder", location=[1, 2, -30],
          rotation=prop_rotation_for_axis(1, 0, 0), scale=[0.9, 0.9, 2.5],
          material="steel")
    assert len(env.enqueued) == 1
    cmd = env.enqueued[0]
    assert cmd.type == "SpawnAsset"
    assert cmd.strings[0] == PROP_MESHES["cylinder"]
    assert cmd.strings[2] == "m"                       # client units
    assert cmd.numbers[0] == [1.0, 2.0, -30.0]          # location
    rpy = cmd.numbers[1]
    assert abs(rpy[1] - 89.7) < 0.5                     # near-horizontal pitch
    assert cmd.numbers[2] == [0.9, 0.9, 2.5]            # scale


def test_asset_spawner_rejects_unknown_prop():
    env = _FakeEnv()
    spawn = make_asset_spawner(env, _FakeHoloocean)
    with pytest.raises(CustomEngineError, match="no mesh mapping"):
        spawn("torus", location=[0, 0, 0], rotation=[0, 0, 0], scale=[1, 1, 1])

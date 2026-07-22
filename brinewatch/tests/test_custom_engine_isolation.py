from types import SimpleNamespace

import pytest

from brinewatch.simulation.custom_engine import (
    CustomEngine,
    CustomEngineError,
    attach_custom_environment,
    editor_launch_args,
    prepare_isolated_runtime,
    validate_instance_id,
)


def test_instance_id_rejects_empty_or_unsafe_values():
    for value in ("", "short", "space is unsafe", "../escape", "bad:colon"):
        with pytest.raises(CustomEngineError):
            validate_instance_id(value)
    assert validate_instance_id("brinewatch-a1b2c3") == "brinewatch-a1b2c3"


def test_runtime_has_separate_directories_and_manifest(tmp_path):
    runtime = prepare_isolated_runtime("brinewatch-test01", tmp_path)
    paths = {
        runtime.work_dir,
        runtime.output_dir,
        runtime.temp_dir,
        runtime.cache_dir,
        runtime.octree_dir,
        runtime.log_dir,
    }
    assert len(paths) == 6
    assert all(path.is_dir() for path in paths)
    manifest = (runtime.root / "session_manifest.json").read_text(encoding="utf-8")
    assert "HOLODECK_SEMAPHORE_SERVERbrinewatch-test01" in manifest
    assert "HOLODECK_MEMbrinewatch-test01_" in manifest


def test_editor_arguments_namespace_ipc_cache_and_log(tmp_path):
    editor = tmp_path / "UnrealEditor.exe"
    editor.touch()
    project = tmp_path / "engine" / "Holodeck.uproject"
    project.parent.mkdir()
    project.touch()
    engine = CustomEngine(
        root=project.parent,
        uproject=project,
        client_src=None,
        octrees_dir=project.parent / "Octrees",
    )
    args = editor_launch_args(
        engine,
        editor_exe=str(editor),
        instance_id="brinewatch-test02",
        octree_cache_root=tmp_path / "private-octrees",
        absolute_log=tmp_path / "logs" / "engine.log",
    )
    assert "--HolodeckUUID=brinewatch-test02" in args
    assert any(arg.startswith("-OctreeCacheRoot=") for arg in args)
    assert any(arg.startswith("-abslog=") for arg in args)


def test_attach_passes_uuid_to_environment(monkeypatch):
    captured = {}

    class FakeEnvironment:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    fake_holoocean = SimpleNamespace(
        environments=SimpleNamespace(HoloOceanEnvironment=FakeEnvironment))
    monkeypatch.setenv("BRINEWATCH_HOLOOCEAN_INSTANCE_ID", "brinewatch-test03")
    scenario = {"ticks_per_sec": 30, "frames_per_sec": False, "agents": []}
    attach_custom_environment(fake_holoocean, scenario)
    assert captured["uuid"] == "brinewatch-test03"
    assert captured["scenario"] is scenario
    assert captured["start_world"] is False

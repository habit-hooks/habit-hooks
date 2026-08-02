"""Unit tests for the plugin loader's per-sensor override handling.

The loader turns a plugin's ``config.toml`` and its ``sensors/<name>.toml`` specs
into ``Part`` objects, applying the project's ``[sensors.<name>]`` overrides. Each
override key it reads must reach the ``Part`` the runner then executes.
"""

from __future__ import annotations

from pathlib import Path

from plugin_fixture import loader_for, write_plugin, write_project_config


def _one_sensor(project_dir: Path, sensor_toml: str) -> object:
    write_plugin(
        project_dir,
        "fixt",
        {"config.toml": 'sensors = ["s"]', "sensors/s.toml": sensor_toml},
    )
    return loader_for(project_dir).load_plugin("fixt").sensors[0]


def test_disabled_override_drops_the_sensor(tmp_path: Path) -> None:
    write_plugin(
        tmp_path,
        "fixt",
        {"config.toml": 'sensors = ["s"]', "sensors/s.toml": 'command = "echo"'},
    )
    write_project_config(tmp_path, 'plugins = ["fixt"]\n[sensors.s]\ndisabled = true')
    assert loader_for(tmp_path).load_plugin("fixt").sensors == []


def test_args_override_reaches_the_part(tmp_path: Path) -> None:
    part = _one_sensor(tmp_path, 'command = "echo ${args}"\nargs = ["--from-spec"]')
    assert part.args == ["--from-spec"]

    write_project_config(
        tmp_path, 'plugins = ["fixt"]\n[sensors.s]\nargs = ["--from-project"]'
    )
    assert loader_for(tmp_path).load_plugin("fixt").sensors[0].args == ["--from-project"]


def test_sensor_spec_files_default_reaches_the_part(tmp_path: Path) -> None:
    part = _one_sensor(tmp_path, 'command = "echo ${files}"\nfiles = ["src/**"]')
    assert part.files == ["src/**"]


def test_files_override_replaces_the_sensor_spec_default(tmp_path: Path) -> None:
    _one_sensor(tmp_path, 'command = "echo ${files}"\nfiles = ["src/**"]')
    write_project_config(tmp_path, 'plugins = ["fixt"]\n[sensors.s]\nfiles = ["lib/**"]')
    assert loader_for(tmp_path).load_plugin("fixt").sensors[0].files == ["lib/**"]


def test_a_sensor_declaring_no_files_carries_none(tmp_path: Path) -> None:
    part = _one_sensor(tmp_path, 'command = "echo ${files}"')
    assert part.files is None

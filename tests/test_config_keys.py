"""Unit tests for the unknown-key guard, at every level and for every binary.

A key nothing consumes is a typo or a documented-but-dead key, so it is rejected
by name rather than ignored (#102) — and the rejection names the binary that
loaded the config, since all three console scripts share this one loader.
Loading and merging a config that passes the guard is ``test_config.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from habit_hooks.config import load_config
from plugin_fixture import write_plugin, write_project_config


def _project(tmp_path: Path, body: str) -> Path:
    write_project_config(tmp_path, body)
    return tmp_path


def _load(project_dir: Path) -> None:
    load_config(project_dir, program="habit-sensors")


def test_an_unknown_root_key_is_rejected_by_name(tmp_path: Path) -> None:
    # `[sensor.knip]` singular lands `sensor` as an unknown root key.
    project = _project(tmp_path, 'plugins = ["generic"]\n[sensor.knip]\ndisabled = true')
    with pytest.raises(SystemExit, match=r"'sensor'"):
        _load(project)


def test_an_unknown_scope_key_is_rejected_by_name(tmp_path: Path) -> None:
    project = _project(tmp_path, "[scope]\nchange_dOnly = true")
    with pytest.raises(SystemExit, match=r"'change_dOnly'"):
        _load(project)


def test_an_unknown_sensor_key_is_rejected_by_name(tmp_path: Path) -> None:
    project = _project(tmp_path, "[sensors.line-count]\ndisable = true")
    with pytest.raises(SystemExit, match=r"'disable'"):
        _load(project)


def test_an_unknown_smell_key_is_rejected_by_name(tmp_path: Path) -> None:
    project = _project(tmp_path, '[smells.duplicated-code]\nseverty = "suggested"')
    with pytest.raises(SystemExit, match=r"'severty'"):
        _load(project)


def test_an_unknown_plugin_config_key_is_rejected_by_name(tmp_path: Path) -> None:
    """The guard fires on plugin-shipped config too, not only the project's."""
    project = _project(tmp_path, 'plugins = ["alpha"]')
    write_plugin(project, "alpha", {"config.toml": 'sensors = ["s"]\nsensorz = ["oops"]'})
    with pytest.raises(SystemExit, match=r"'sensorz'"):
        _load(project)


@pytest.mark.parametrize("program", ["habit-sensors", "habit-mapper", "habit-snooze"])
def test_a_rejected_key_names_the_binary_that_loaded_it(
    tmp_path: Path, program: str
) -> None:
    """One loader serves all three binaries, so a hardcoded prefix sent a
    ``habit-mapper --config`` user hunting through habit-sensors for their typo."""
    project = _project(tmp_path, '[smells.duplicated-code]\nseverty = "suggested"')
    with pytest.raises(SystemExit) as failure:
        load_config(project, program=program)
    assert str(failure.value).startswith(f"{program}: unknown config key")

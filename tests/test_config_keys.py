"""Unit tests for the unknown-key guard, at every level.

A key nothing consumes is a typo or a documented-but-dead key, so it is rejected
by name rather than ignored (#102). The rejection names no binary here: all three
console scripts share this one loader, so the name is added where the failure is
printed (``test_cli.py``). Loading and merging a config that passes the guard is
``test_config.py``.
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
    load_config(project_dir)


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


def test_an_unknown_uncoached_value_is_rejected_with_the_valid_ones(
    tmp_path: Path,
) -> None:
    """A value nothing consumes is a typo the same way a key is (#111). Reading
    ``"supress"`` as the default would silently mean ``enforce``, which is the
    behaviour the project was trying to turn off."""
    project = _project(tmp_path, 'uncoached = "supress"')
    with pytest.raises(SystemExit, match=r"'supress'") as failure:
        _load(project)
    message = str(failure.value)
    assert "'uncoached'" in message
    assert "'enforce', 'ignore', 'suggest'" in message


def test_an_unknown_plugin_config_key_is_rejected_by_name(tmp_path: Path) -> None:
    """The guard fires on plugin-shipped config too, not only the project's."""
    project = _project(tmp_path, 'plugins = ["alpha"]')
    write_plugin(project, "alpha", {"config.toml": 'sensors = ["s"]\nsensorz = ["oops"]'})
    with pytest.raises(SystemExit, match=r"'sensorz'"):
        _load(project)


def test_a_rejection_names_no_binary(tmp_path: Path) -> None:
    """The loader is also imported by a project's own transformer, which is a
    separate process and no binary of ours (#109), so it takes no argument for a
    name — and cannot invent one for the message either."""
    project = _project(tmp_path, '[smells.duplicated-code]\nseverty = "suggested"')
    with pytest.raises(SystemExit) as failure:
        load_config(project)
    assert str(failure.value).startswith("unknown config key")

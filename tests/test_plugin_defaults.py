"""Unit tests for what the active plugins contribute to a project's config.

``files``, ``[runners]`` and ``detectors`` are the root keys a plugin supplies:
what it calls source, what it can run a fix with, and what it needs installed.
Each merges across the ``plugins`` list in order, and the project's own config
settles the two it may also name. Loading the project's own config is
``test_config.py``; refusing a config is ``test_config_schema.py``.
"""

from __future__ import annotations

from pathlib import Path

from habit_hooks.config import Config, Detector, load_config
from plugin_fixture import write_plugin, write_project_config


def _project(tmp_path: Path, body: str) -> Path:
    write_project_config(tmp_path, body)
    return tmp_path


def _plugin(project_dir: Path, name: str, body: str) -> None:
    """A fixture plugin, shadowing any installed one of that name."""
    write_plugin(project_dir, name, {"config.toml": body})


def _load(project_dir: Path) -> Config:
    return load_config(project_dir)


def test_plugin_files_merge_in_plugins_order_without_repeating(tmp_path: Path) -> None:
    """Order is load-bearing: a later negation must be able to undo an earlier glob."""
    project = _project(tmp_path, 'plugins = ["alpha", "beta"]')
    _plugin(project, "alpha", 'files = ["src/**", "shared/**"]')
    _plugin(project, "beta", 'files = ["shared/**", "lib/**"]')
    assert _load(project).files == ["src/**", "shared/**", "lib/**"]


def test_the_projects_own_files_replace_the_plugins(tmp_path: Path) -> None:
    project = _project(tmp_path, 'plugins = ["alpha"]\nfiles = ["only/**"]')
    _plugin(project, "alpha", 'files = ["src/**"]')
    assert _load(project).files == ["only/**"]


def test_a_plugin_declaring_no_files_states_no_opinion(tmp_path: Path) -> None:
    project = _project(tmp_path, 'plugins = ["alpha"]')
    _plugin(project, "alpha", 'sensors = ["noop"]')
    assert _load(project).files is None


def test_plugin_runners_merge_under_the_project(tmp_path: Path) -> None:
    """A plugin ships its own ``[runners]``; the project's win per extension."""
    project = _project(tmp_path, 'plugins = ["alpha"]\n[runners]\npy = "python3"')
    _plugin(project, "alpha", '[runners]\npy = "python2"\nlua = "lua"')
    assert _load(project).runners == {"py": "python3", "lua": "lua"}


def test_plugin_runners_apply_when_the_project_declares_none(tmp_path: Path) -> None:
    project = _project(tmp_path, 'plugins = ["alpha"]')
    _plugin(project, "alpha", '[runners]\npy = "python3"')
    assert _load(project).runners == {"py": "python3"}


def test_the_first_plugin_wins_a_runner_extension(tmp_path: Path) -> None:
    """``plugins`` order is a priority, as it is for guide lookup."""
    project = _project(tmp_path, 'plugins = ["alpha", "beta"]')
    _plugin(project, "alpha", '[runners]\npy = "alpha-py"')
    _plugin(project, "beta", '[runners]\npy = "beta-py"')
    assert _load(project).runners == {"py": "alpha-py"}


def _declaring(*entries: str) -> str:
    return f"detectors = [{', '.join(entries)}]"


def _entry(name: str, kind: str = "command") -> str:
    return f'{{ name = "{name}", kind = "{kind}", install = "get {name}" }}'


def _detectors(project_dir: Path) -> list[Detector]:
    return _load(project_dir).plugin_detectors


def test_a_plugin_declaring_no_detectors_contributes_none(tmp_path: Path) -> None:
    project = _project(tmp_path, 'plugins = ["alpha"]')
    _plugin(project, "alpha", 'sensors = ["noop"]')
    assert _detectors(project) == []


def test_a_declared_detector_keeps_its_kind_and_install_command(tmp_path: Path) -> None:
    """All three fields travel: what to look for, how to look for it, and the
    command that installs it — the last is the whole point of declaring it."""
    project = _project(tmp_path, 'plugins = ["alpha"]')
    _plugin(project, "alpha", _declaring(_entry("ts-morph", "node-module")))
    assert _detectors(project) == [
        Detector(name="ts-morph", kind="node-module", install="get ts-morph")
    ]


def test_plugin_detectors_merge_in_plugins_order(tmp_path: Path) -> None:
    project = _project(tmp_path, 'plugins = ["alpha", "beta"]')
    _plugin(project, "alpha", _declaring(_entry("ruff"), _entry("deptry")))
    _plugin(project, "beta", _declaring(_entry("jscpd")))
    assert [d.name for d in _detectors(project)] == ["ruff", "deptry", "jscpd"]


def test_two_plugins_naming_one_detector_declare_it_once(tmp_path: Path) -> None:
    """Two languages needing the same tool must not ask twice; the first plugin
    to name it decides how it is installed, as it does for a runner."""
    other = '{ name = "jq", kind = "command", install = "other" }'
    project = _project(tmp_path, 'plugins = ["alpha", "beta"]')
    _plugin(project, "alpha", _declaring(_entry("jq")))
    _plugin(project, "beta", _declaring(other))
    assert _detectors(project) == [Detector(name="jq", kind="command", install="get jq")]


def test_one_name_under_two_kinds_is_two_detectors(tmp_path: Path) -> None:
    """``eslint`` on PATH and ``eslint`` resolvable by node are different
    questions with different answers, so the kind is part of the identity."""
    project = _project(tmp_path, 'plugins = ["alpha"]')
    _plugin(project, "alpha", _declaring(_entry("eslint"), _entry("eslint", "node-module")))
    assert [d.kind for d in _detectors(project)] == ["command", "node-module"]

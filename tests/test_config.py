"""Unit tests for loading a project's own TOML config.

These pin the loader's behaviour on the file a project writes: its defaults when
there is none, and the nested construction when there is. What the active plugins
contribute to it is ``test_plugin_defaults.py``; refusing a config — an unknown
key, an unknown value, a file that is not TOML at all — is
``test_config_schema.py``.
"""

from __future__ import annotations

from pathlib import Path

from habit_hooks.config import (
    Config,
    ScopeDefaults,
    SensorOverride,
    SmellOverride,
    load_config,
)


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / ".habit-hooks" / "config.toml"
    path.parent.mkdir(parents=True)
    path.write_text(body)
    return tmp_path


def _load(project_dir: Path) -> Config:
    return load_config(project_dir)


def test_missing_config_yields_defaults(tmp_path: Path) -> None:
    config = _load(tmp_path)
    assert config.plugins == ["generic"]
    assert config.transformers == ["snooze"]
    assert config.files is None
    assert config.uncoached == "suggest"
    assert config.runners == {}
    assert config.sensors == {}
    assert config.smells == {}


def test_missing_config_yields_the_scope_defaults(tmp_path: Path) -> None:
    scope = _load(tmp_path).scope
    assert isinstance(scope, ScopeDefaults)
    assert scope.changedOnly is False
    assert scope.autoBranchOffMain is False
    assert scope.branchBase == "main"
    assert scope.mainBranch == "main"


def test_a_caller_that_names_no_program_still_loads(tmp_path: Path) -> None:
    """The call a project's own transformer makes, spelled out rather than routed
    through ``_load``. A transformer is a separate process, and importing this
    function is the only way one has ever had to read ``[scope] branchBase``, so a
    required keyword argument here broke every caller outside this repo (#109).
    """
    assert load_config(tmp_path).scope.branchBase == "main"


_POPULATED_CONFIG = """
plugins = ["python", "generic"]
transformers = ["squash"]
files = ["src/**"]

[scope]
changedOnly = true
branchBase = "develop"

[runners]
py = "python3"

[sensors.line-count]
args = ["--max", "300"]
disabled = true

[smells.long-file]
severity = "error"
guide = "style-nit.md"
"""


def _load_populated(tmp_path: Path) -> Config:
    return _load(_write(tmp_path, _POPULATED_CONFIG))


def test_populated_top_level_fields_load(tmp_path: Path) -> None:
    config = _load_populated(tmp_path)
    assert config.plugins == ["python", "generic"]
    assert config.transformers == ["squash"]
    assert config.files == ["src/**"]


def test_populated_scope_merges_with_defaults(tmp_path: Path) -> None:
    scope = _load_populated(tmp_path).scope
    assert scope.changedOnly is True
    assert scope.branchBase == "develop"
    assert scope.mainBranch == "main"  # untouched default


def test_populated_runners_load(tmp_path: Path) -> None:
    assert _load_populated(tmp_path).runners == {"py": "python3"}


def test_populated_sensor_override_loads(tmp_path: Path) -> None:
    override = _load_populated(tmp_path).sensors["line-count"]
    assert isinstance(override, SensorOverride)
    assert override.args == ["--max", "300"]
    assert override.disabled is True
    assert override.files is None


def test_populated_smell_override_loads(tmp_path: Path) -> None:
    smell = _load_populated(tmp_path).smells["long-file"]
    assert isinstance(smell, SmellOverride)
    assert smell.severity == "error"
    assert smell.guide == "style-nit.md"
    assert smell.disabled is None


def test_a_valid_config_still_loads_after_the_unknown_key_guard(tmp_path: Path) -> None:
    """The guard must not reject any key the loader actually consumes."""
    _load_populated(tmp_path)  # must not raise


def test_direct_defaults_are_independent_instances() -> None:
    a = Config()
    b = Config()
    a.plugins.append("mutated")
    assert b.plugins == ["generic"]
    assert a.scope is not b.scope

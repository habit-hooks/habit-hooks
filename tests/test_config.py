"""Unit tests for the TOML config loader.

These pin the loader's behaviour: defaults, nested construction, and silently
ignoring unknown keys at every level.
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


def test_missing_config_yields_defaults(tmp_path: Path) -> None:
    config = load_config(tmp_path)
    assert config.plugins == ["generic"]
    assert config.transformers == []
    assert config.files is None
    assert config.runners == {}
    assert config.sensors == {}
    assert config.smells == {}
    assert isinstance(config.scope, ScopeDefaults)
    assert config.scope.changedOnly is False
    assert config.scope.autoBranchOffMain is False
    assert config.scope.branchBase == "main"
    assert config.scope.mainBranch == "main"


def test_known_fields_load(tmp_path: Path) -> None:
    project = _write(
        tmp_path,
        """
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
title = "Too long"
""",
    )
    config = load_config(project)
    assert config.plugins == ["python", "generic"]
    assert config.transformers == ["squash"]
    assert config.files == ["src/**"]
    assert config.scope.changedOnly is True
    assert config.scope.branchBase == "develop"
    assert config.scope.mainBranch == "main"  # untouched default
    assert config.runners == {"py": "python3"}

    override = config.sensors["line-count"]
    assert isinstance(override, SensorOverride)
    assert override.args == ["--max", "300"]
    assert override.disabled is True
    assert override.command is None

    smell = config.smells["long-file"]
    assert isinstance(smell, SmellOverride)
    assert smell.severity == "error"
    assert smell.title == "Too long"
    assert smell.guide is None


def test_unknown_keys_are_ignored_at_every_level(tmp_path: Path) -> None:
    project = _write(
        tmp_path,
        """
plugins = ["generic"]
totallyUnknownTopLevel = "ignored"

[scope]
changedOnly = true
bogusScopeKey = 123

[sensors.line-count]
args = ["--max", "10"]
mysteryKey = "ignored"

[smells.long-file]
severity = "warning"
whatIsThis = true
""",
    )
    config = load_config(project)  # must not raise
    assert config.plugins == ["generic"]
    assert config.scope.changedOnly is True
    assert config.sensors["line-count"].args == ["--max", "10"]
    assert config.smells["long-file"].severity == "warning"
    # Unknown keys are dropped, not readable back.
    assert not hasattr(config, "totallyUnknownTopLevel")
    assert not hasattr(config.scope, "bogusScopeKey")


def test_direct_defaults_are_independent_instances() -> None:
    a = Config()
    b = Config()
    a.plugins.append("mutated")
    assert b.plugins == ["generic"]
    assert a.scope is not b.scope

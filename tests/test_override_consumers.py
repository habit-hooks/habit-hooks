"""Guard: no override dataclass field may be documented but read by nothing.

Parameterised over every field of ``SensorOverride`` and ``SmellOverride``, each
test asserts the field maps to a probe that proves the field changes behaviour.
Add a field without a probe and the build fails — the loader-level answer to
"a documented key is read by nothing" (#87).
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest
from attrs import fields

from habit_hooks.config import Config, SensorOverride, SmellOverride
from habit_hooks.rendering import guide_names, is_disabled, severity_of
from plugin_fixture import loader_for, write_plugin, write_project_config


def _sensor_under(tmp_path: Path, override_line: str) -> list:
    """The loaded sensors of a one-sensor fixture plugin under one override line."""
    write_plugin(
        tmp_path,
        "fixt",
        {"config.toml": 'sensors = ["s"]', "sensors/s.toml": 'command = "echo"'},
    )
    write_project_config(tmp_path, f'plugins = ["fixt"]\n[sensors.s]\n{override_line}')
    return loader_for(tmp_path).load_plugin("fixt").sensors


_SENSOR_CONSUMERS: dict[str, Callable[[Path], bool]] = {
    "disabled": lambda tmp: _sensor_under(tmp, "disabled = true") == [],
    "args": lambda tmp: _sensor_under(tmp, 'args = ["--z"]')[0].args == ["--z"],
    "files": lambda tmp: _sensor_under(tmp, 'files = ["a/**"]')[0].files == ["a/**"],
}


@pytest.mark.parametrize("name", [f.name for f in fields(SensorOverride)])
def test_every_sensor_override_field_has_a_consumer(name: str, tmp_path: Path) -> None:
    probe = _SENSOR_CONSUMERS.get(name)
    assert probe is not None, f"SensorOverride.{name} is read by nothing"
    assert probe(tmp_path)


def _smell(field: str, value: object) -> Config:
    return Config(smells={"x": SmellOverride(**{field: value})})


_SMELL_CONSUMERS: dict[str, Callable[[], bool]] = {
    "severity": lambda: severity_of("x", _smell("severity", "suggested")) == "suggested",
    "guide": lambda: guide_names("x", _smell("guide", "g.md")) == ["g.md"],
    "disabled": lambda: is_disabled("x", _smell("disabled", True)),
}


@pytest.mark.parametrize("name", [f.name for f in fields(SmellOverride)])
def test_every_smell_override_field_has_a_consumer(name: str) -> None:
    probe = _SMELL_CONSUMERS.get(name)
    assert probe is not None, f"SmellOverride.{name} is read by nothing"
    assert probe()

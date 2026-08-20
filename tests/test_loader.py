"""Unit tests for the plugin loader's per-sensor override handling.

The loader turns a plugin's ``config.toml`` and its ``sensors/<name>.toml`` specs
into ``Part`` objects, applying the project's ``[sensors.<name>]`` overrides. Each
override key it reads must reach the ``Part`` the runner then executes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from habit_hooks.cli import ConfigError
from plugin_fixture import loader_for, write_plugin, write_project_config


def _one_sensor(project_dir: Path, sensor_toml: str) -> object:
    write_plugin(
        project_dir,
        "fixt",
        {"config.toml": 'sensors = ["s"]', "sensors/s.toml": sensor_toml},
    )
    return loader_for(project_dir).load_plugin("fixt").sensors[0]


def test_an_argv_spec_reaches_the_part_as_a_list(tmp_path: Path) -> None:
    """The other way to spell a recipe: an argument list, spawned as it stands
    rather than read by a shell."""
    part = _one_sensor(tmp_path, 'argv = ["ruff", "check", "${files}"]')

    assert part.argv == ["ruff", "check", "${files}"]
    assert part.command is None


def test_a_spec_spelling_both_command_and_argv_is_refused_by_name(
    tmp_path: Path,
) -> None:
    """Which of the two runs would otherwise be settled by whichever the code
    looked at first — so it is refused where the author can still see both."""
    with pytest.raises(ConfigError) as refusal:
        _one_sensor(tmp_path, 'command = "ruff"\nargv = ["ruff"]')

    assert str(refusal.value).startswith("sensor 's' spells both 'command' and 'argv'")


def test_a_spec_spelling_neither_is_refused_by_name(tmp_path: Path) -> None:
    """A part that states what it is and never what it does. It used to be a
    ``KeyError`` traceback out of the loader, which is the first-contact
    failure #114 was about."""
    with pytest.raises(ConfigError) as refusal:
        _one_sensor(tmp_path, 'files = ["src/**"]')

    assert str(refusal.value).startswith("sensor 's' spells neither 'command' nor 'argv'")


def test_a_transformer_missing_its_recipe_is_named_a_transformer(
    tmp_path: Path,
) -> None:
    """The refusal names the kind it refused, so a reader is looking for the
    right file — a transformer has no ``[sensors.<name>]`` to edit."""
    write_plugin(
        tmp_path,
        "fixt",
        {"config.toml": 'sensors = []', "transformers/t.toml": 'files = ["src/**"]'},
    )

    with pytest.raises(ConfigError) as refusal:
        loader_for(tmp_path).resolve_part(["fixt"], "transformers", "t")

    assert str(refusal.value).startswith("transformer 't' spells neither")


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


def test_an_emptied_args_override_clears_the_specs_default(tmp_path: Path) -> None:
    """``args = []`` is a value, not an absence, so it clears what the plugin
    shipped. That is the only way out for a consumer whose run is refused over a
    plugin's own unusable ``args`` default (``command_text.reject_unusable_args``),
    so the loader must not read the empty list as "nothing set" and fall through.
    """
    _one_sensor(tmp_path, 'command = "echo"\nargs = ["--from-spec"]')
    write_project_config(tmp_path, 'plugins = ["fixt"]\n[sensors.s]\nargs = []')

    assert loader_for(tmp_path).load_plugin("fixt").sensors[0].args == []


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


def test_a_sensor_spec_that_is_not_toml_is_refused_by_name(tmp_path: Path) -> None:
    """A part spec is hand-written too, so it earns the same refusal the project
    config does (#114) rather than a ``tomllib`` traceback: one shared read means
    every TOML this tool opens answers a slip in it the same way."""
    spec = tmp_path / ".habit-hooks" / "fixt" / "sensors" / "s.toml"

    with pytest.raises(SystemExit) as failure:
        _one_sensor(tmp_path, 'command = "echo')

    assert str(failure.value) == (
        f"{spec}: invalid TOML: Unterminated string (at end of document)"
    )

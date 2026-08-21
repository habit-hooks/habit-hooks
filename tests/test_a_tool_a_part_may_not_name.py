"""The two tool names a recipe can never expand, refused as the config loads.

``${detector:<name>}`` stands for the file this project runs for one of its
plugins' declared tools (``test_a_part_names_its_tool``). Two names have no such
file and never will, whatever is installed: one no active plugin declares, and
one declared as a ``node-module`` — a package node resolves from the project,
never a program on a search path.

Both are a plugin's packaging mistake rather than anything a machine could fix,
so both are refused where a plugin author can still see the recipe: a
``ConfigError`` at exit 2, before anything is spawned. Whoever reads it, though,
is a consumer whose whole run has just stopped — every plugin's parts are loaded
together — and the recipe is not theirs to edit, so each refusal ends with the
one thing they can do: switch that part off. A tool that is declared, is a
command, and is merely not installed is neither of these, and stays the ordinary
missing tool ``test_a_tool_a_part_cannot_run`` covers.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from bare_machine import project_with_no_tools
from detector_declarations import PMD, TS_MORPH, declaring
from plugin_fixture import loader_for, one_sensor, write_plugin, write_project_config

from habit_hooks.cli import ConfigError


def test_a_tool_no_plugin_declares_is_refused_when_the_config_loads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nothing knows where to get a tool nobody declared, so there is no install
    command to offer and no run to be had — and the plugin that shipped the
    recipe is the only place it can be fixed. The refusal names what this run
    does declare, which is the list the missing line was meant to join."""
    project = project_with_no_tools(tmp_path, monkeypatch)

    with pytest.raises(ConfigError) as refusal:
        one_sensor(project, 'argv = ["${detector:jscpd}"]', declaring(PMD))

    assert str(refusal.value) == (
        "sensor 's' names ${detector:jscpd}, which no active plugin declares: a "
        "plugin names the tools its sensors reach for in its config.toml "
        "'detectors', and this run declares pmd (command) — disable the sensor "
        "with [sensors.s] disabled = true"
    )


def test_a_plugin_that_declares_nothing_is_told_it_declared_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The commonest way to earn that refusal is writing the recipe and
    forgetting the declaration, so the empty list has to read as one."""
    project = project_with_no_tools(tmp_path, monkeypatch)

    with pytest.raises(ConfigError) as refusal:
        one_sensor(project, 'argv = ["${detector:jscpd}"]')

    assert "this run declares none" in str(refusal.value)


def test_a_placeholder_naming_nothing_is_a_typo_and_not_an_argument(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``${detector:}`` names no tool, and the one thing it must never do is
    survive expansion: a placeholder handed to a tool verbatim is an argument
    nobody wrote, arriving as an unopenable filename long after the slip."""
    project = project_with_no_tools(tmp_path, monkeypatch)

    with pytest.raises(ConfigError) as refusal:
        one_sensor(project, 'argv = ["${detector:}"]', declaring(PMD))

    assert "sensor 's' names ${detector:}, which no active plugin declares" in str(
        refusal.value
    )


def test_switching_the_sensor_off_really_does_clear_the_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The line each refusal ends on has to work, or a consumer is left holding a
    stopped run and an instruction that changes nothing. A disabled sensor is
    dropped before its spec is resolved at all (``PluginLoader.load_plugin``), so
    the recipe that could not be expanded is never read."""
    project = project_with_no_tools(tmp_path, monkeypatch)
    write_plugin(
        project,
        "fixt",
        {
            "config.toml": f'sensors = ["s"]\n{declaring(PMD)}',
            "sensors/s.toml": 'argv = ["${detector:jscpd}"]',
        },
    )
    write_project_config(project, 'plugins = ["fixt"]\n[sensors.s]\ndisabled = true')

    assert loader_for(project).load_plugin("fixt").sensors == []


def test_a_module_node_reads_is_no_command_and_is_refused_as_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ``node-module`` is looked for by asking node to resolve it from the
    project, which answers about a package and not about a file to spawn. A name
    of that kind on a search path would be some other program entirely, so it is
    refused rather than resolved into whatever happens to answer to it."""
    project = project_with_no_tools(tmp_path, monkeypatch)

    with pytest.raises(ConfigError) as refusal:
        one_sensor(project, 'argv = ["${detector:ts-morph}"]', declaring(TS_MORPH))

    assert str(refusal.value) == (
        "sensor 's' names ${detector:ts-morph}, but 'ts-morph' is declared "
        "'node-module', not 'command': only a command names a file this run can "
        "spawn, and a module is read by node from the project, never spawned by "
        "name — disable the sensor with [sensors.s] disabled = true"
    )

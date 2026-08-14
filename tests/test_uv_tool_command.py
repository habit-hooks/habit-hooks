"""Unit tests for what the one command a uv tool is offered has to name.

``uv tool install`` rebuilds the environment rather than adding to it, so what
the command leaves out is what it deletes: every case here is about a plugin
that has to survive the install of another one. habit-hooks spells its own
plugins in the brackets and brings the ones it depends on unasked; a plugin
somebody else wrote has to be named outright, and a plugin kept in the project
must not be named at all.

Which installations are offered this command rather than a pip one is
``test_plugin_install.py``.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from habit_hooks import resolve
from habit_hooks.initialise import plan
from habit_hooks.plugin_install import install_commands
from plugin_fixture import write_plugin, write_project_config


@pytest.fixture
def installed_machine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Callable[..., None]:
    """Hands a case the plugins this machine holds, each with its distribution.

    Named rather than left to the one the suite runs on, where ``uv sync``
    installs all four: which plugins the command has to name *is* the question
    here, so it cannot be answered by whatever happens to be lying about. The
    distribution is named beside the plugin because an installed plugin is
    reinstalled under the name it was shipped under, never under a spelling of
    its own name.
    """

    def holding(**distributions: str) -> None:
        dirs = {}
        for plugin in distributions:
            directory = tmp_path / plugin
            directory.mkdir()
            (directory / "config.toml").write_text("")
            dirs[plugin] = directory
        monkeypatch.setattr(resolve, "installed_plugin_dirs", lambda: dirs)
        monkeypatch.setattr(
            resolve, "installed_plugin_distributions", lambda: distributions
        )

    return holding


def test_every_installed_plugin_has_a_distribution_name() -> None:
    """A plugin that drops out of the map is one the command names by the old
    guess again, silently and only for that plugin — so the property worth
    holding is that the two answers about an installation cover the same
    plugins. What the name has to *be* is the case below; this one is that there
    is one.
    """
    assert set(resolve.installed_plugin_distributions()) == set(
        resolve.installed_plugin_dirs()
    )


def test_an_installed_plugin_is_reinstalled_under_the_name_it_arrived_under(
    installed_machine: Callable[..., None], uv_tool_installed: None
) -> None:
    """Nothing obliges a plugin's distribution to be named after its entry
    point, and ``habit-hooks-<plugin>`` for one that is not fails the whole
    command on a name no index has heard of — taking the plugin that really is
    missing down with it, which is the failure the vendored carve-out exists to
    avoid."""
    installed_machine(cobol="acme-hooks-cobol", generic="habit-hooks-generic")

    assert install_commands(("cobol", "python", "generic"), ("python",)) == (
        "uv tool install 'habit-hooks[python]' --with acme-hooks-cobol",
    )


def test_every_missing_plugin_is_installed_in_one_command(
    uv_tool_installed: None,
) -> None:
    """One command per plugin would leave only the last one installed — the
    state init exists to report, arrived at by following init."""
    planned = ("python", "typescript", "generic")

    assert install_commands(planned, ("python", "typescript")) == (
        "uv tool install 'habit-hooks[python,typescript]'",
    )


def test_the_plugins_this_project_already_has_are_named_again(
    uv_tool_installed: None,
) -> None:
    """The rebuild is what makes the command name every planned plugin: naming
    only the missing one would install it over the one already there."""
    planned = ("python", "typescript", "generic")

    assert install_commands(planned, ("python",)) == (
        "uv tool install 'habit-hooks[python,typescript]'",
    )


def test_a_plugin_habit_hooks_does_not_ship_is_named_beside_the_extras(
    uv_tool_installed: None,
) -> None:
    """A third-party plugin has no spelling in habit-hooks' own brackets, and a
    second command would undo the first — so it joins this one."""
    assert install_commands(("cobol", "python", "generic"), ("cobol",)) == (
        "uv tool install 'habit-hooks[python]' --with habit-hooks-cobol",
    )


def test_a_plugin_habit_hooks_does_not_ship_is_kept_once_it_is_installed(
    uv_tool_installed: None,
) -> None:
    """The rebuild deletes whatever the command leaves out, and a third-party
    plugin has no brackets to be carried along in — so leaving it out here is
    init printing the command that produces the state init exists to report."""
    assert install_commands(("cobol", "python", "generic"), ("python",)) == (
        "uv tool install 'habit-hooks[python]' --with habit-hooks-cobol",
    )


def test_a_uv_tool_needing_no_shipped_plugin_names_habit_hooks_plainly(
    uv_tool_installed: None,
) -> None:
    """Empty brackets are an extra nothing provides, which uv warns about and
    then installs around. ``generic`` needs no naming either way: habit-hooks
    depends on it, so every install of the tool brings it."""
    assert install_commands(("cobol", "generic"), ("cobol",)) == (
        "uv tool install habit-hooks --with habit-hooks-cobol",
    )


def test_a_plugin_name_cannot_say_something_the_config_did_not_to_uv(
    uv_tool_installed: None,
) -> None:
    """The command is handed to a shell, and the names in it come out of a
    config that arrives with a cloned repository. ``$(...)`` is substituted
    inside double quotes as readily as outside them, so the repository's own
    command would run the moment the reader answered ``y``."""
    hostile = "$(touch pwned)"

    assert install_commands((hostile, "generic"), (hostile,)) == (
        "uv tool install habit-hooks --with 'habit-hooks-$(touch pwned)'",
    )


def test_a_plugin_this_project_already_has_is_named_again(
    init_project: Path, installed_machine: Callable[..., None], uv_tool_installed: None
) -> None:
    """The command is built from what the machine holds, not from what is
    missing: leave the installed plugin out and the rebuild deletes it."""
    installed_machine(cobol="habit-hooks-cobol", generic="habit-hooks-generic")
    write_project_config(init_project, 'plugins = ["cobol", "python", "generic"]')

    assert plan(init_project).plugin_installs == (
        "uv tool install 'habit-hooks[python]' --with habit-hooks-cobol",
    )


def test_a_plugin_only_the_project_next_door_runs_is_kept(
    init_project: Path, installed_machine: Callable[..., None], uv_tool_installed: None
) -> None:
    """One uv tool environment serves the whole machine, so a command naming
    only this project's plugins uninstalls the ones another project runs — the
    trap the README warns about, sprung by the tool that exists to spare it."""
    installed_machine(python="habit-hooks-python", generic="habit-hooks-generic")
    write_project_config(init_project, 'plugins = ["php", "generic"]')

    assert plan(init_project).plugin_installs == (
        "uv tool install 'habit-hooks[python,php]'",
    )


def test_a_plugin_kept_in_the_project_is_left_out_of_the_command(
    init_project: Path, pluginless_machine: None, uv_tool_installed: None
) -> None:
    """PyPI has never heard of the plugin somebody vendored under
    ``.habit-hooks/``, so naming it would fail the whole install — taking the
    plugin that really is missing down with it."""
    write_plugin(init_project, "cobol", {"config.toml": ""})
    write_project_config(init_project, 'plugins = ["cobol", "python", "generic"]')

    assert plan(init_project).plugin_installs == (
        "uv tool install 'habit-hooks[python]'",
    )

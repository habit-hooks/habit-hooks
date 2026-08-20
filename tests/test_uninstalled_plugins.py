"""Unit tests for the plugins ``habit-hooks init`` reports nobody has.

The other half of what can stand in a setup's way, and the worse half: a missing
tool costs one sensor's findings, where a plugin neither installed nor vendored
stops the first run dead on ``Resolver.require_plugin``. A setup that reported
nothing missing sent someone off to work that out for themselves — which is the
report this whole command was built in answer to.

The tool half is ``test_missing_tools.py``; the command that installs one is
``test_plugin_install.py``.
"""

from __future__ import annotations

from pathlib import Path

from habit_hooks.initialise import plan
from plugin_fixture import write_plugin, write_project_config

_NEEDING_A_TOOL = (
    'detectors = [{ name = "wobble", kind = "command",'
    ' install = "brew install wobble" }]'
)


def test_a_planned_plugin_nobody_has_is_what_stands_in_the_way(
    init_project: Path, pluginless_machine: None
) -> None:
    """Planning a plugin says nothing about being able to run it, and until this
    the difference only showed up on the first run, as a failure."""
    (init_project / "pyproject.toml").write_text("[project]\n", encoding="utf-8")

    planned = plan(init_project)

    assert planned.plugins == ("python", "generic")
    assert planned.uninstalled_plugins == ("python",)
    assert planned.plugin_installs != ()


def test_a_vendored_plugin_is_one_this_project_has(
    init_project: Path, pluginless_machine: None
) -> None:
    """The resolver's own question, so being told to install a plugin you keep
    under ``.habit-hooks/`` cannot happen — ``generic`` is vendored here and
    nothing at all is installed."""
    assert plan(init_project).uninstalled_plugins == ()


def test_a_configured_plugin_nobody_has_is_reported_by_a_re_run(
    init_project: Path,
) -> None:
    """The doctor case: the config names it, the run dies on it, and nothing
    said so before the run."""
    write_project_config(init_project, 'plugins = ["cobol", "generic"]')

    assert plan(init_project).uninstalled_plugins == ("cobol",)


def test_the_plugins_are_installed_before_the_tools_they_bring(
    init_project: Path, pluginless_machine: None
) -> None:
    """A plugin declares tools of its own, which cannot be looked for until the
    plugin is there — so its install comes first, and a tool's after it."""
    write_plugin(init_project, "generic", {"config.toml": _NEEDING_A_TOOL})
    write_project_config(init_project, 'plugins = ["cobol", "generic"]')

    planned = plan(init_project)

    assert planned.installs == (*planned.plugin_installs, "brew install wobble")

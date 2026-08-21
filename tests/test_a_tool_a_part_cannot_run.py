"""A tool a plugin declared, a command, and simply not installed on this machine.

``${detector:<name>}`` stands for the file this project runs for one of its
plugins' declared tools (``test_a_part_names_its_tool``), and two names can never
stand for a file at all, whatever is installed (``test_a_tool_a_part_may_not_name``).
This is the third answer and the everyday one: declared, a command, and absent —
the missing tool every first run meets. It is nobody's config mistake, so nothing
is refused; the part fails by name, its findings drop, and the reader is told what
to install and how to stop running it in the meantime.

Every recipe here is the shape a shipped sensor has — a helper of its own, handed
the tool it is to spawn — and never the tool as ``argv[0]``. That one fails at the
spawn whatever the loader knew, so it would prove nothing; a helper handed a name
it cannot run prints its clean ``[]`` and the run believes it, which is the
false-clean these cases are about.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from bare_machine import project_with_no_tools
from detector_declarations import JSCPD, PMD, declaring
from executable_stub import write_stub
from plugin_fixture import loader_for, one_sensor, write_plugin, write_project_config

from habit_hooks.scope import Scope
from habit_hooks.sensors.execution import Execution
from habit_hooks.sensors.model import Part, Run


def _recipe(*arguments: str) -> str:
    """A helper that reports a clean run, handed ``arguments`` to spawn."""
    handed = "".join(f', "{argument}"' for argument in arguments)
    return f"argv = [\"${{python}}\", \"-c\", \"print('[]')\"{handed}]"


def _run(project: Path, part: Part) -> Run:
    """What running ``part`` over one file comes to."""
    scope = Scope(files=["src/a.py"])
    return Execution(project_dir=project, scope=scope).run_sensors([part])


def _one_transformer(project: Path, recipe: str, plugin_toml: str) -> Part:
    """The single transformer of a fixture plugin, as a run's loader builds it.

    Resolved against the run's plugins rather than any one of them, which is how
    a root transformer is reached (``sensors.run_sensors``).
    """
    write_project_config(project, 'plugins = ["fixt"]')
    write_plugin(
        project,
        "fixt",
        {"config.toml": f"sensors = []\n{plugin_toml}", "transformers/t.toml": recipe},
    )
    return loader_for(project).resolve_part(["fixt"], "transformers", "t")


def test_a_part_naming_no_tool_answers_for_none_of_its_plugins_tools(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A part answers for the tools it reaches for and for no others.

    Its plugin declares what everything in it may need, and neither of these two
    is installed — but this sensor names neither, so neither is its problem. Were
    the plugin's whole declaration attached to every part, one absent tool would
    fail the sensors that never wanted it.
    """
    project = project_with_no_tools(tmp_path, monkeypatch)
    part = one_sensor(project, _recipe(), declaring(JSCPD, PMD))

    assert part.detectors == {}
    assert _run(project, part).notices == []


def test_a_sensor_naming_a_tool_the_project_cannot_run_fails_by_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The sensor fails by name, its findings drop, and the reader is told what
    to install. Installing it is the whole of the fix, which is what the second
    half shows."""
    project = project_with_no_tools(tmp_path, monkeypatch)
    recipe = _recipe("${detector:jscpd}")

    run = _run(project, one_sensor(project, recipe, declaring(JSCPD)))

    assert run.failed
    assert run.findings == []
    assert run.notices == [
        "habit-sensors: sensor 's' needs the 'jscpd' command, which is not "
        "installed — install it, or disable the sensor with [sensors.s] "
        "disabled = true"
    ]

    write_stub(project / "node_modules" / ".bin", "jscpd")

    assert _run(project, one_sensor(project, recipe, declaring(JSCPD))).notices == []


def test_the_tool_a_part_is_told_about_is_the_absent_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A recipe naming two is answered about whichever one is missing, not
    whichever one it named first — otherwise a reader is sent to install a tool
    already sitting in their project, and the one they actually need goes
    unnamed."""
    project = project_with_no_tools(tmp_path, monkeypatch)
    write_stub(project / "node_modules" / ".bin", "jscpd")
    recipe = _recipe("${detector:jscpd}", "${detector:pmd}")

    run = _run(project, one_sensor(project, recipe, declaring(JSCPD, PMD)))

    assert run.notices == [
        "habit-sensors: sensor 's' needs the 'pmd' command, which is not "
        "installed — install it, or disable the sensor with [sensors.s] "
        "disabled = true"
    ]


def test_a_transformer_naming_one_is_told_how_to_drop_a_transformer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A transformer names its tools the same way and fails the same way, but it
    has no ``[sensors.<name>]`` switch of its own — it runs because the root
    ``transformers`` list names it, so that list is the action it is given."""
    project = project_with_no_tools(tmp_path, monkeypatch)
    part = _one_transformer(project, _recipe("${detector:jscpd}"), declaring(JSCPD))
    execution = Execution(project_dir=project, scope=Scope(files=[]))

    _, notices = execution.apply_transformers([part], [])

    assert notices == [
        "habit-sensors: transformer 't' needs the 'jscpd' command, which is not "
        "installed — install it, or drop 't' from the root transformers list"
    ]

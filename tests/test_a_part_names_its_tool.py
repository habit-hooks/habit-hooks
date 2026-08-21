"""The tool a part's recipe names, and the file this project runs for it.

A sensor spawns tools its plugin did not ship, and the plugin declares each of
them as a detector. ``${detector:<name>}`` is how the recipe asks for one: it
stands for the very file the setup cleared that tool by, so a helper is handed
its tool rather than a name to look up again — the lookup a bare name loses on
Windows, where npm installs every Node tool as a ``.cmd`` shim no spawn finds by
name. A name the recipe may not use at all is ``test_a_tool_a_part_may_not_name``;
a tool this project simply has not got is ``test_a_tool_a_part_cannot_run``.

Nothing here is pinned to a platform, because nothing here has two answers.
What an installed tool looks like is the real host's question
(``executable_stub``), and every case asserts the file that host's own lookup
answers with — ``jscpd`` on a Mac, ``jscpd.cmd`` on Windows, the same ``jscpd``
stem in either. The one bin directory both platforms spell alike,
``node_modules/.bin``, is where each case installs, so no venv layout is being
assumed either. The single case that *is* pinned says why.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from bare_machine import machine_bin, project_with_no_tools
from detector_declarations import JSCPD, PMD, declaring
from executable_stub import write_stub
from platform_probe import A_MACHINE_THAT_DOES_NOT
from plugin_fixture import one_sensor

from habit_hooks.scope import Scope
from habit_hooks.sensors.execution import Execution
from habit_hooks.sensors.model import Part


def _argv(project: Path, part: Part) -> list[str]:
    """The argv spawning ``part`` in ``project`` would carry."""
    return Execution(project_dir=project, scope=Scope(files=[]))._expand(part)


def test_a_named_tool_expands_to_the_file_this_project_runs_for_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The whole point: the recipe carries a file, not a name still to be found."""
    project = project_with_no_tools(tmp_path, monkeypatch)
    bin_dir = project / "node_modules" / ".bin"
    write_stub(bin_dir, "jscpd")
    part = one_sensor(
        project, 'argv = ["${detector:jscpd}", "--reporters", "json"]', declaring(JSCPD)
    )

    argv = _argv(project, part)

    assert Path(argv[0]).parent == bin_dir
    assert Path(argv[0]).stem == "jscpd"
    assert argv[1:] == ["--reporters", "json"]


def test_a_named_tool_fills_in_inside_the_argument_that_names_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """It stands for one string, so it is substituted where it stands rather than
    expanded into arguments of its own — a helper told which tool to spawn takes
    it as the one value it is, ``--jscpd=<file>`` included."""
    project = project_with_no_tools(tmp_path, monkeypatch)
    bin_dir = project / "node_modules" / ".bin"
    write_stub(bin_dir, "jscpd")
    part = one_sensor(
        project, 'argv = ["node", "h.cjs", "--jscpd=${detector:jscpd}"]', declaring(JSCPD)
    )

    named = _argv(project, part)[2].removeprefix("--jscpd=")

    assert Path(named).parent == bin_dir
    assert Path(named).stem == "jscpd"


def test_each_named_tool_expands_to_its_own_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A recipe may need two of them, and each stands for itself."""
    project = project_with_no_tools(tmp_path, monkeypatch)
    bin_dir = project / "node_modules" / ".bin"
    write_stub(bin_dir, "jscpd")
    write_stub(bin_dir, "pmd")
    part = one_sensor(
        project,
        'argv = ["${detector:jscpd}", "--against", "${detector:pmd}"]',
        declaring(JSCPD, PMD),
    )

    argv = _argv(project, part)

    assert [Path(argv[0]).stem, Path(argv[2]).stem] == ["jscpd", "pmd"]
    assert {Path(argv[0]).parent, Path(argv[2]).parent} == {bin_dir}


def test_a_tool_named_twice_stands_for_the_same_file_at_both(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A recipe may also need to say one of them twice — a helper told which tool
    to spawn and what to call it in its own output. It is one tool, looked for
    once, and filled in wherever it stands, so the two can never come to differ.
    """
    project = project_with_no_tools(tmp_path, monkeypatch)
    bin_dir = project / "node_modules" / ".bin"
    write_stub(bin_dir, "jscpd")
    part = one_sensor(
        project,
        'argv = ["${detector:jscpd}", "--called", "${detector:jscpd}"]',
        declaring(JSCPD),
    )

    argv = _argv(project, part)

    assert list(part.detectors) == ["jscpd"]
    assert Path(argv[0]).parent == bin_dir
    assert argv[2] == argv[0]


@A_MACHINE_THAT_DOES_NOT
def test_a_shell_recipe_splices_the_file_quoted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A tool's own path is text a shell reads, so it is quoted like every other
    string spliced into a ``command`` — a machine keeping its tools under
    ``Program Files`` would otherwise hand ``bash`` two words.

    Pinned to a host that spells a command as the filename it is: a shell recipe
    is refused on Windows anyway (``posix_shell``), so the platform that can run
    one is the platform this is answered for.
    """
    machine = machine_bin(tmp_path) / "with a space"
    project = project_with_no_tools(tmp_path, monkeypatch)
    monkeypatch.setenv("PATH", str(machine))
    write_stub(machine, "jscpd")
    part = one_sensor(project, 'command = "${detector:jscpd} --json"', declaring(JSCPD))

    assert _argv(project, part)[2] == f"'{machine / 'jscpd'}' --json"

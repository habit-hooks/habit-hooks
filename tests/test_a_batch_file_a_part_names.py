"""A tool a part names is a batch file, and the part's arguments are its shell's.

``test_batch_file_arguments`` is this guarantee where the batch file is the
part's own program. No shipped sensor spells its tool there: each is a helper of
its own, and the tool it spawns — PMD's ``pmd.bat``, npm's ``jscpd.CMD`` —
reads those arguments one process further in, where reading ``argv[0]`` alone
sees nothing at all. A recipe reaches that program by naming it
(``${detector:<name>}``); no shipped sensor names one yet, so what is guarded
here is still guarded for them by their plugin's own ``tool_spawn`` copy.

Only a tool the config declared and this project resolved to a file counts as a
program here. A scoped source file called ``build.bat`` is data, and refusing an
argument on its account would cost a project a run it should have had.

Nothing pins a platform, for the reason that file gives: the guard reads the
resolved file's own extension and never asks where it is running. The tool is
declared by a name carrying that extension so both platforms' lookups answer
with the one file the case wrote (``executable_stub.write_batch_stub``).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from batch_tool_project import (
    BATCH_TOOL,
    PLAIN_TOOL,
    batch_sensor,
    installing_a_batch_tool,
    recipe,
)
from bare_machine import project_with_no_tools
from detector_declarations import declaring
from executable_stub import write_batch_stub, write_stub
from platform_probe import A_MACHINE_THAT_DOES_NOT, A_SHELL_TO_RUN_IT_WITH
from plugin_fixture import one_sensor, one_transformer

from habit_hooks.scope import Scope
from habit_hooks.sensors.execution import Execution
from habit_hooks.sensors.model import Part, Run

def _run(project: Path, part: Part, *files: str) -> Run:
    """What running ``part`` over a scope of ``files`` comes to."""
    scope = Scope(files=list(files))
    return Execution(project_dir=project, scope=scope).run_sensors([part])


def test_a_batch_tool_a_part_names_reads_that_parts_arguments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The helper this sensor spawns is no batch file, so ``argv[0]`` says the
    arguments are safe — and the tool it forwards them to is one, so they are
    not. The sensor fails by name, saying which argument and which program."""
    project = installing_a_batch_tool(tmp_path, monkeypatch)
    tool = project / "node_modules" / ".bin" / "probe.cmd"

    run = _run(project, batch_sensor(project), "src/a&echo.>PWNED&.py")

    assert run.findings == []
    assert run.notices == [
        "habit-sensors: sensor 's' cannot pass 'src/a&echo.>PWNED&.py' to "
        f"{str(tool)!r}: a batch file is run by cmd.exe, which would read that "
        "as its own syntax rather than as text — rename the file, or keep it "
        "out of the scope with [files]"
    ]


def test_a_batch_tool_is_found_wherever_a_part_names_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every program the arguments reach is asked about, not one end of the list.

    A part naming two tools puts the batch one where it is neither the program
    spawned nor the last named, which is what tells a guard that walks them
    apart from one that samples an end — and a sensor reaching for a second
    tool is ordinary, so the middle is not a contrived position.
    """
    project = installing_a_batch_tool(tmp_path, monkeypatch)
    write_stub(project / "node_modules" / ".bin", "probe2")
    part = one_sensor(
        project,
        recipe("${detector:probe.cmd}", "${detector:probe2}"),
        declaring(BATCH_TOOL, PLAIN_TOOL.replace("probe", "probe2")),
    )

    assert _run(project, part, "src/a&b.py").failed


def test_an_argument_of_only_text_still_reaches_a_batch_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The refusal must cost a project nothing it had: a batch program handed
    arguments that are only text still runs, ``build.bat`` among them."""
    project = installing_a_batch_tool(tmp_path, monkeypatch)

    run = _run(project, batch_sensor(project), "src/a.py", "build.bat")

    assert run.notices == []


def test_a_scoped_batch_file_is_data_and_never_a_program(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A part naming no tool at all is handed both a ``build.bat`` and a
    filename carrying an ``&``, and neither is anything but a filename: nothing
    is between them and a helper that spawns nothing."""
    project = project_with_no_tools(tmp_path, monkeypatch)
    part = one_sensor(project, recipe())

    run = _run(project, part, "build.bat", "src/a&b.py")

    assert run.notices == []


@A_MACHINE_THAT_DOES_NOT
def test_a_tool_that_is_no_batch_file_reads_the_same_argument_as_a_filename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An ``&`` in a filename is a filename, which is what every POSIX run of
    every sensor depends on. Pinned to a host where an install is the filename
    it is: on Windows every stub an install writes is itself a ``.cmd``, which
    is the case the rest of this file is about."""
    project = project_with_no_tools(tmp_path, monkeypatch)
    write_stub(project / "node_modules" / ".bin", "probe")
    part = one_sensor(project, recipe("${detector:probe}"), declaring(PLAIN_TOOL))

    run = _run(project, part, "src/a&b.py")

    assert run.notices == []


@A_SHELL_TO_RUN_IT_WITH
def test_a_shell_recipe_is_text_to_split_and_not_arguments(tmp_path: Path) -> None:
    """A ``command`` part hands its recipe to a shell, which splits the text and
    passes the words on itself — so the two elements ``bash -c`` carries are the
    recipe, and refusing it for the ``>`` in it would refuse every pipeline
    anyone writes. There is no such part where a batch file exists in any case:
    ``posix_shell`` refuses one before it spawns, which is why this needs a
    machine with a shell on it — the only case here that keeps the machine's own
    ``PATH``, for the ``bash`` on it. The tool is still the project's own, which
    ``tool_search_path`` looks for ahead of anything installed on the machine."""
    project = tmp_path / "project"
    write_batch_stub(project / "node_modules" / ".bin", "probe")
    shell_recipe = 'command = "${detector:probe.cmd} ${files} >/dev/null; printf \'[]\'"'
    part = one_sensor(project, shell_recipe, declaring(BATCH_TOOL))

    run = _run(project, part, "src/a.py")

    assert run.notices == []


def test_a_tool_nobody_installed_is_still_the_missing_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A part that cannot run at all is answered for before its arguments are:
    the reader is told what to install, not about a shell nothing reached."""
    project = project_with_no_tools(tmp_path, monkeypatch)

    run = _run(project, batch_sensor(project), "src/a&b.py")

    assert run.notices == [
        "habit-sensors: sensor 's' needs the 'probe.cmd' command, which is not "
        "installed — install it, or disable the sensor with [sensors.s] "
        "disabled = true"
    ]


def test_a_transformer_naming_one_is_refused_under_its_own_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A transformer is handed the scope and its tools exactly as a sensor is,
    so it is refused exactly as one — named for the part that earned it."""
    project = installing_a_batch_tool(tmp_path, monkeypatch)
    part = one_transformer(
        project, recipe("${detector:probe.cmd}"), declaring(BATCH_TOOL)
    )
    execution = Execution(project_dir=project, scope=Scope(files=["src/a&b.py"]))

    _, notices = execution.apply_transformers([part], [])

    assert notices == [
        "habit-sensors: transformer 't' cannot pass 'src/a&b.py' to "
        f"{str(project / 'node_modules' / '.bin' / 'probe.cmd')!r}: a batch file "
        "is run by cmd.exe, which would read that as its own syntax rather than "
        "as text — rename the file, or keep it out of the scope with [files]"
    ]

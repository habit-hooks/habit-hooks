"""A filename handed to a batch file is data there too.

``tests/test_execution.py``'s ``test_a_filename_can_never_execute_a_command`` is
the POSIX half of one guarantee: a scoped path comes out of the work tree, so a
file added by a pull request from a fork must never run its author's command on
a reviewer's machine. This is the other half. ``CreateProcess`` runs a ``.bat``
or ``.cmd`` through ``cmd.exe``, whose syntax is not what ``subprocess`` quotes
for (CVE-2024-24576), so an argument carrying it is refused before anything is
spawned (``sensors/batch_shell.py``).

Nothing here pins a platform, because nothing here answers differently on one:
the guard reads the resolved program's own extension and never asks where it is
running. That is what lets the refusal be shown on a Mac and on the Windows leg
by the same assertions — only the last step, whether ``cmd.exe`` really would
have obeyed the injected command, belongs to the host that has one.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from bare_machine import project_with_no_tools
from executable_stub import write_batch_stub

from habit_hooks.scope import Scope
from habit_hooks.sensors.execution import Execution
from habit_hooks.sensors.model import Part, SensorError
from habit_hooks.sensors.spawn import Spawner


def _project_with_a_batch_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path]:
    """A project whose only installed tool is a batch file called ``probe``."""
    project = project_with_no_tools(tmp_path, monkeypatch)
    return project, write_batch_stub(project / "node_modules" / ".bin", "probe")


def test_a_filename_can_never_become_cmd_syntax(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The Windows twin of ``test_a_filename_can_never_execute_a_command``.

    The scoped path carries no space, so ``subprocess`` would not even quote it:
    ``cmd.exe`` would read the ``&`` and run the rest as a command of its own.
    The sensor fails instead, saying which argument and why — and the marker
    that command would have written is not there. Off Windows that last
    assertion is free, since no shell was ever going to read the argument; it is
    the one line of this that only the Windows leg can really answer.
    """
    project, _ = _project_with_a_batch_tool(tmp_path, monkeypatch)
    marker = project / "PWNED"
    part = Part(name="probe", directory=project, argv=["probe.cmd", "${files}"])
    execution = Execution(
        project_dir=project, scope=Scope(files=["src/a&echo.>PWNED&.py"])
    )

    with pytest.raises(SensorError) as refusal:
        execution.run_sensor(part)

    assert not marker.exists()
    assert str(refusal.value).startswith(
        "sensor 'probe' cannot pass 'src/a&echo.>PWNED&.py' to "
    )


def test_a_batch_file_still_runs_when_every_argument_is_only_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The refusal must cost a Windows project nothing it had: the shims npm and
    PMD install are batch files, and ordinary arguments still reach them."""
    project, tool = _project_with_a_batch_tool(tmp_path, monkeypatch)

    result = Spawner(project).run(["probe.cmd", "--max", "200", "src/a.py"])

    assert result.returncode == 0
    assert result.args == [str(tool), "--max", "200", "src/a.py"]


def test_a_batch_file_named_by_its_own_path_is_refused_the_same(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A part may spell a program as a path rather than as a name, and the two
    reach the spawn by different branches — what reads the arguments is the same
    shell either way, so both branches pass through the refusal."""
    project, tool = _project_with_a_batch_tool(tmp_path, monkeypatch)

    with pytest.raises(SensorError):
        Spawner(project).run([str(tool), "src/a&b.py"])


def test_the_first_unreadable_argument_is_the_one_named(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One name, not a list: the first is enough to act on, and a scope can hold
    thousands of paths."""
    project, _ = _project_with_a_batch_tool(tmp_path, monkeypatch)

    with pytest.raises(SensorError) as refusal:
        Spawner(project).run(["probe.cmd", "fine.py", "a&b.py", "c|d.py"])

    assert "'a&b.py'" in str(refusal.value)


@pytest.mark.parametrize("syntax", ["&", "|", "<", ">", "^", '"', "%", "\n", "\r"])
def test_every_character_cmd_exe_reads_as_syntax_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, syntax: str
) -> None:
    """The set is the decision, so each member of it is asserted. ``%`` earns its
    place separately from the rest: ``%VAR%`` is expanded by ``cmd.exe`` even
    inside the quotes ``subprocess`` puts round an argument, so quoting is not
    what makes it safe."""
    project, _ = _project_with_a_batch_tool(tmp_path, monkeypatch)

    with pytest.raises(SensorError):
        Spawner(project).run(["probe.cmd", f"src/a{syntax}b.py"])


@pytest.mark.parametrize("punctuation", ["(", ")", "!", "'", "$", " ", "#"])
def test_punctuation_cmd_exe_reads_as_text_is_left_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, punctuation: str
) -> None:
    """The exclusions are a decision too, and ``(`` is why they matter: every
    32-bit tool on Windows lives under ``C:\\Program Files (x86)``, so refusing
    a parenthesis would refuse the ordinary case. None of these opens a command,
    a variable or a redirection where an argument stands (``!`` only under
    ``cmd /V:ON``, which nothing here spawns)."""
    project, tool = _project_with_a_batch_tool(tmp_path, monkeypatch)

    result = Spawner(project).run(["probe.cmd", f"src/a{punctuation}b.py"])

    assert result.args == [str(tool), f"src/a{punctuation}b.py"]


def test_the_same_argument_is_ordinary_text_for_a_program_that_is_no_batch_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nothing stands between the spawn and an ordinary program, so an ``&`` in a
    filename is a filename — which is what every POSIX run of every sensor
    depends on. The interpreter running this suite is the one program both
    platforms agree is not a batch file."""
    project = project_with_no_tools(tmp_path, monkeypatch)

    result = Spawner(project).run(
        [sys.executable, "-c", "import sys; print(sys.argv[1])", "src/a&b.py"]
    )

    assert result.stdout.strip() == "src/a&b.py"


def test_a_refused_argument_fails_that_sensor_and_leaves_the_run_standing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """It is a part failure, not a crash: the notice names the sensor, the run
    is failed rather than reported clean, and no traceback reaches a reader."""
    project, tool = _project_with_a_batch_tool(tmp_path, monkeypatch)
    part = Part(name="probe", directory=project, argv=["probe.cmd", "${files}"])
    execution = Execution(project_dir=project, scope=Scope(files=["src/a&b.py"]))

    run = execution.run_sensors([part])

    assert run.failed
    assert run.findings == []
    assert run.notices == [
        f"habit-sensors: sensor 'probe' cannot pass 'src/a&b.py' to {str(tool)!r}: "
        "a batch file is run by cmd.exe, which would read that as its own "
        "syntax rather than as text — rename the file, or keep it out of the "
        "scope with [files]"
    ]

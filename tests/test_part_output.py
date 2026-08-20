"""What a broken sensor's output becomes: the notice the run reports.

Running a part is ``test_sensor_deadline.py`` and ``test_sensor_environment.py``;
this is the reading back — the ``part_output`` question of how a failure is
described once the command has exited. A command nobody installed is the one
failure the tool has no words of its own for, because it never ran, so
habit-hooks supplies them (#114).
"""

from __future__ import annotations

from pathlib import Path

from habit_hooks.scope import Scope
from habit_hooks.sensors.execution import Execution
from habit_hooks.sensors.model import Part


def _sensor_notice(tmp_path: Path, command: str) -> str:
    """The one notice a sensor running ``command`` leaves on its failed run."""
    return _only_notice(Part(name="probe", command=command, directory=tmp_path), tmp_path)


def _only_notice(part: Part, project_dir: Path) -> str:
    """The one notice ``part`` leaves on the failed run it produces."""
    execution = Execution(project_dir=project_dir, scope=Scope(files=["src/a.py"]))

    run = execution.run_sensors([part])

    assert run.findings == []
    assert run.failed
    assert len(run.notices) == 1
    return run.notices[0]


def test_a_sensor_whose_tool_is_not_installed_names_the_tool(tmp_path: Path) -> None:
    """The commonest failure on a machine that has just met habit-hooks answered
    as whatever the shell or the sensor's own helper happened to print — for
    jscpd, twenty lines of Python internals whose punchline named the binary only
    as a filename that could not be found (#114). It is still the same notice +
    failed run any broken sensor produces; the notice now says what to install,
    and what to do instead of installing it."""
    notice = _sensor_notice(tmp_path, "no-such-tool-here --json ${files}")

    assert notice == (
        "habit-sensors: sensor 'probe' needs the 'no-such-tool-here' command, "
        "which is not installed — install it, or disable the sensor with "
        "[sensors.probe] disabled = true"
    )


def test_a_tool_missing_from_inside_a_pipeline_is_named_too(tmp_path: Path) -> None:
    """The shipped ``ruff`` and ``eslint`` sensors both pipe their tool through
    ``jq`` under ``set -o pipefail``, so the missing half is never the last thing
    the shell mentions — the whole command's output is searched for it."""
    pipeline = "set -o pipefail\nno-such-tool-here | jq ."

    assert "needs the 'no-such-tool-here' command" in _sensor_notice(tmp_path, pipeline)


def test_a_sensor_that_broke_some_other_way_still_quotes_itself_back(
    tmp_path: Path,
) -> None:
    """Only a command that was never found is answered in our own words. Every
    other failure is the tool diagnosing itself, and that is the one thing a
    reader can act on, so it is still carried into the notice verbatim."""
    notice = _sensor_notice(tmp_path, "echo 'cannot reach registry' >&2; exit 1")

    assert notice.startswith("habit-sensors: sensor 'probe' failed:")
    assert "cannot reach registry" in notice


def test_a_sensor_at_the_truncation_boundary_is_still_quoted_whole(
    tmp_path: Path,
) -> None:
    """Truncating only pays for itself once the excerpt it produces — head, an
    elision line, and tail — is actually shorter than the diagnosis it would
    replace. At 21 lines the excerpt would also come to 21 lines, so nothing is
    dropped, and nothing is lost for free."""
    storm = 'for i in $(seq 1 21); do echo "line $i" >&2; done; exit 1'

    notice = _sensor_notice(tmp_path, storm)
    lines = notice.splitlines()

    assert "line 1" in lines
    assert "line 21" in lines
    assert "omitted" not in notice


def test_a_sensor_one_line_past_the_boundary_finally_elides(tmp_path: Path) -> None:
    """One line more and the excerpt is finally shorter than the diagnosis it
    replaces, so it elides — head, tail, and the middle it stands in for."""
    storm = 'for i in $(seq 1 22); do echo "line $i" >&2; done; exit 1'

    notice = _sensor_notice(tmp_path, storm)
    lines = notice.splitlines()

    assert "line 1" in lines
    assert "line 11" not in lines
    assert "line 22" in lines
    assert "... 2 lines omitted ..." in lines


def test_a_sensor_whose_last_line_carries_the_diagnosis_still_quotes_it(
    tmp_path: Path,
) -> None:
    """A Python traceback names its exception on its *last* line, not its first.

    A chatty tool that dies with a traceback — the shape every Python-helper
    sensor's own crash takes, deptry included — buries its one useful line at
    the bottom of output that easily runs past the quoted budget. Quoting only
    the head, as this once did, guarantees that line is exactly the one
    dropped; the tail has to survive too. The exception text lives only in the
    helper script's stderr, not in the command that ran it, so this fails for
    the right reason rather than by the command line echoing itself back.
    """
    (tmp_path / "crash.py").write_text(
        "import sys\n"
        "for i in range(1, 25):\n"
        '    print(f"noise {i}", file=sys.stderr)\n'
        'raise RuntimeError("boom: the real reason")\n',
        encoding="utf-8",
    )

    notice = _sensor_notice(tmp_path, "${python} ${dir}/crash.py")

    assert "boom: the real reason" in notice


def test_an_argv_sensor_names_its_missing_tool_in_the_very_same_words(
    tmp_path: Path,
) -> None:
    """An argv part has no shell to say ``command not found`` for it — the
    spawn just fails — and a generic "could not run" would leave the commonest
    first-contact failure (#114) undiagnosed on exactly the platform that has
    no shell to fall back on. So the answer is the shell's own, word for word:
    which form a sensor is spelled in must not change what a newcomer reads."""
    part = Part(
        name="probe", directory=tmp_path, argv=["no-such-tool-here", "--json"]
    )

    assert _only_notice(part, tmp_path) == (
        "habit-sensors: sensor 'probe' needs the 'no-such-tool-here' command, "
        "which is not installed — install it, or disable the sensor with "
        "[sensors.probe] disabled = true"
    )


def test_a_spawn_refused_for_another_reason_is_not_called_a_missing_tool(
    tmp_path: Path,
) -> None:
    """``Popen`` raises the same ``FileNotFoundError`` for a missing program and
    for a project directory that is gone, and only the spawning layer can tell
    them apart. Reading the second as the first would name a tool that is
    installed and send the reader off to install it again."""
    part = Part(name="probe", directory=tmp_path, argv=["printf", "[]"])

    notice = _only_notice(part, tmp_path / "deleted")

    assert "needs the" not in notice
    assert notice.startswith("habit-sensors: sensor 'probe' could not run: printf '[]'")

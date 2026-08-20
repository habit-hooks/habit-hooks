"""How a work-tree-sized file list reaches a sensor: chunked into command lines
the operating system will carry, measured as the shell will spell them, and
degrading into a notice when the spawn is refused anyway (issue #96)."""

from __future__ import annotations

from pathlib import Path

from habit_hooks.argv_budget import ARGUMENT_BUDGET
from habit_hooks.scope import Scope
from habit_hooks.sensors.execution import Execution
from habit_hooks.sensors.model import Part


def test_a_scope_past_the_argv_budget_runs_in_chunks(tmp_path: Path) -> None:
    """A file list too long for one command line must not raise ``OSError``.

    Above the platform's single-argument cap the whole list in one ``bash -c``
    argument fails the spawn; ``_safe_sensor`` never caught that, so it escaped
    as a traceback out of an ordinary CI-sized run. Chunked, every file reaches
    a sensor invocation and every invocation's findings come back.
    """
    (tmp_path / "count.py").write_text(
        "import sys, json\n"
        'print(json.dumps([{"smell": "s", "count": len(sys.argv) - 1,'
        ' "issues": []}]))\n',
        encoding="utf-8",
    )
    part = Part(
        name="probe", command="${python} ${dir}/count.py ${files}", directory=tmp_path
    )
    files = [f"generated/module_{index:06d}.py" for index in range(8_000)]
    assert sum(len(name) + 1 for name in files) > 2 * ARGUMENT_BUDGET
    execution = Execution(project_dir=tmp_path, scope=Scope(files=files))

    findings = execution.run_sensor(part)

    assert len(findings) > 1
    assert sum(finding["count"] for finding in findings) == len(files)


def test_the_budget_counts_a_path_as_the_command_line_spells_it(
    tmp_path: Path,
) -> None:
    """Quoting inflates, and it is the quoted text the spawn has to carry.

    ``${files}`` is spliced into one ``bash -c`` argument *quoted* — two wrapping
    quotes per name, and every ``'`` in a name costing five bytes. Budgeting the
    raw names let a chunk measured at 99KB reach the spawn as 137KB, past Linux's
    128KB cap on a single argument, where the refused spawn's ``OSError`` escaped
    as a traceback. So the chunking has to measure what it is actually sending.
    """
    part = Part(
        name="probe", command="${python} ${dir}/count.py ${files}", directory=tmp_path
    )
    files = [f"src/it's/o'clock_{index:05d}.py" for index in range(3_800)]
    assert sum(len(name) + 1 for name in files) < ARGUMENT_BUDGET
    execution = Execution(project_dir=tmp_path, scope=Scope(files=files))

    commands = execution._sensor_commands(part)

    assert len(commands) > 1
    assert max(len(command) for command in commands) <= ARGUMENT_BUDGET


def test_a_spawn_the_system_refuses_is_a_notice_not_a_traceback(
    tmp_path: Path,
) -> None:
    """The budget is a guess about the operating system; the answer must not be.

    Whatever the chunking believes, only the spawn itself knows — an argument
    list past a cap this budget guessed wrong, a project directory deleted
    mid-run, no ``bash`` on PATH. ``OSError`` was caught nowhere between here and
    ``main``, so it escaped ``pool.map`` as a traceback instead of the notice +
    failed run every other spawn failure produces.
    """
    part = Part(name="probe", command="printf '[]'", directory=tmp_path)
    execution = Execution(
        project_dir=tmp_path / "deleted", scope=Scope(files=["src/a.py"])
    )

    run = execution.run_sensors([part])

    assert run.findings == []
    assert run.failed
    assert any("probe" in notice for notice in run.notices)

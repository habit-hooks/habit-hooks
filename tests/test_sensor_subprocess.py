"""Robustness of the sensor subprocess layer: a deadline, a bounded argv, and an
own stdin — the three ways an unusual-but-real run turned into a hang, a
traceback, or a lost run (issue #96)."""

from __future__ import annotations

import contextlib
import os
from collections.abc import Iterator
from pathlib import Path

from habit_hooks.argv_budget import ARGUMENT_BUDGET
from habit_hooks.scope import Scope
from habit_hooks.sensors.execution import Execution
from habit_hooks.sensors.model import Part


@contextlib.contextmanager
def _parent_stdin(data: bytes) -> Iterator[None]:
    """Put ``data`` on fd 0 for the block, so a child inheriting it would read it."""
    read_fd, write_fd = os.pipe()
    os.write(write_fd, data)
    os.close(write_fd)
    saved = os.dup(0)
    os.dup2(read_fd, 0)
    try:
        yield
    finally:
        os.dup2(saved, 0)
        for fd in (saved, read_fd):
            os.close(fd)


def test_a_wedged_sensor_times_out_into_a_failed_run(tmp_path: Path) -> None:
    """A tool that never returns must not hang the hook forever.

    A sensor waiting on input or churning on a pathological repo blocks the git
    hook with no output. The deadline turns that into the same notice + failed
    run any other spawn failure produces, so the run reports and moves on.
    """
    part = Part(name="probe", command="sleep 5; printf '[]'", directory=tmp_path)
    execution = Execution(
        project_dir=tmp_path, scope=Scope(files=["src/a.py"]), timeout=0.2
    )

    run = execution.run_sensors([part])

    assert run.findings == []
    assert run.failed
    assert any("timed out" in notice for notice in run.notices)


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
        ' "issues": []}]))\n'
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


def test_a_sensor_reading_stdin_gets_immediate_eof(tmp_path: Path) -> None:
    """A sensor must never inherit the parent's stdin.

    A ``pre-push`` hook carries refs on stdin and a tool that reads input would
    consume them or block on the prompt. Handing the child an empty, closed
    stdin makes its first read return EOF, whatever the parent's stdin holds.
    """
    (tmp_path / "readall.py").write_text(
        "import sys, json\n"
        "data = sys.stdin.read()\n"
        'print(json.dumps([{"smell": "s", "read": len(data), "issues": []}]))\n'
    )
    part = Part(
        name="probe", command="${python} ${dir}/readall.py", directory=tmp_path
    )
    execution = Execution(project_dir=tmp_path, scope=Scope(files=["src/a.py"]))

    with _parent_stdin(b"refs/heads/main 0000 refs/heads/main 1111\n"):
        findings = execution.run_sensor(part)

    assert findings == [{"smell": "s", "read": 0, "issues": []}]

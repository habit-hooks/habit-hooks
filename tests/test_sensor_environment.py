"""The environment a sensor's command runs in, apart from its deadline: an own
stdin, the project's own tools, and the interpreter settings a helper habit-hooks
ships depends on.

A sensor must never inherit the parent's stdin — a ``pre-push`` hook carries
refs on stdin, and a tool that reads input would consume them or block on a
prompt — and it must reach the tools a project pins under ``.venv/bin`` and
``node_modules/.bin``. The deadline half — a wedged sensor's timeout, and
killing its whole pipeline (issue #96) — is ``test_sensor_deadline.py``.
"""

from __future__ import annotations

import contextlib
import os
import stat
from collections.abc import Iterator
from pathlib import Path

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


def test_a_sensor_reading_stdin_gets_immediate_eof(tmp_path: Path) -> None:
    """A sensor must never inherit the parent's stdin.

    A ``pre-push`` hook carries refs on stdin and a tool that reads input would
    consume them or block on the prompt. Handing the child an empty, closed
    stdin makes its first read return EOF, whatever the parent's stdin holds.
    """
    (tmp_path / "readall.py").write_text(
        "import sys, json\n"
        "data = sys.stdin.read()\n"
        'print(json.dumps([{"smell": "s", "read": len(data), "issues": []}]))\n',
        encoding="utf-8",
    )
    part = Part(
        name="probe", command="${python} ${dir}/readall.py", directory=tmp_path
    )
    execution = Execution(project_dir=tmp_path, scope=Scope(files=["src/a.py"]))

    with _parent_stdin(b"refs/heads/main 0000 refs/heads/main 1111\n"):
        findings = execution.run_sensor(part)

    assert findings == [{"smell": "s", "read": 0, "issues": []}]


def test_a_helper_reaches_its_neighbour_under_a_hardened_environment(
    tmp_path: Path, monkeypatch
) -> None:
    """A shipped Python helper imports the modules beside it by name, and
    ``PYTHONSAFEPATH`` in the consumer's environment must not take that away.

    That variable's whole effect is to drop the script's own directory from
    ``sys.path`` — the one thing a loose helper's ``import <neighbour>`` rests
    on. Inherited, it turned the java sensor into a ``ModuleNotFoundError``
    traceback where the coaching should be.
    """
    (tmp_path / "neighbour.py").write_text('SMELL = "s"\n', encoding="utf-8")
    (tmp_path / "helper.py").write_text(
        "import json\n"
        "from neighbour import SMELL\n"
        'print(json.dumps([{"smell": SMELL, "issues": []}]))\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("PYTHONSAFEPATH", "1")
    part = Part(name="probe", command="${python} ${dir}/helper.py", directory=tmp_path)
    execution = Execution(project_dir=tmp_path, scope=Scope(files=["src/a.py"]))

    assert execution.run_sensor(part) == [{"smell": "s", "issues": []}]


def test_a_sensor_reaches_the_project_s_own_tools(tmp_path: Path) -> None:
    """A project pins its tools under ``.venv/bin`` and ``node_modules/.bin``, and
    the path a run looks along is ``project_paths.tool_search_path`` — the same
    one a setup reports a tool missing from, so the two cannot come to disagree."""
    bin_dir = tmp_path / ".venv" / "bin"
    bin_dir.mkdir(parents=True)
    tool = bin_dir / "habit-probe"
    tool.write_text('#!/bin/sh\nprintf \'[{"smell": "s", "issues": []}]\'\n', encoding="utf-8")
    tool.chmod(tool.stat().st_mode | stat.S_IEXEC)
    part = Part(name="probe", command="habit-probe", directory=tmp_path)
    execution = Execution(project_dir=tmp_path, scope=Scope(files=["src/a.py"]))

    assert execution.run_sensor(part) == [{"smell": "s", "issues": []}]

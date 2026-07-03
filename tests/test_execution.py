"""Unit tests for the sensor command runner's placeholder expansion."""

from __future__ import annotations

import shlex
import sys
from pathlib import Path

from habit_hooks.scope import Scope
from habit_hooks.sensors.execution import Execution
from habit_hooks.sensors.model import Part


def _execution(tmp_path: Path) -> Execution:
    return Execution(project_dir=tmp_path, scope=Scope(files=[]))


def test_expand_replaces_python_with_the_running_interpreter(tmp_path: Path) -> None:
    part = Part(
        name="line-count",
        command="${python} ${dir}/line-count.py",
        directory=tmp_path,
        args=[],
    )

    expanded = _execution(tmp_path)._expand(part)

    assert expanded == f"{shlex.quote(sys.executable)} {tmp_path}/line-count.py"

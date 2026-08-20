"""A detector this plugin does not bring with it must still answer in one line.

``pip install habit-hooks-python`` installs neither ruff nor deptry, so a machine
that has just enabled the plugin is the ordinary case, not the edge one. ruff is
spawned from Python now (it used to be a shell recipe, so the shell answered for
it), and an absent tool is a ``FileNotFoundError`` — twenty lines of internals
would otherwise become the sensor's diagnosis (#114). Mirrors
``test_a_deptry_nobody_installed_is_named.py``.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SENSOR = (
    Path(__file__).resolve().parents[1]
    / "src/habit_hooks_python/sensors/ruff_sensor.py"
)


def test_a_ruff_nobody_installed_answers_the_way_a_shell_does(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(SENSOR)],
        cwd=tmp_path,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env={"PATH": "/nonexistent"},
    )

    assert result.returncode == 2
    assert result.stdout.strip() == ""
    assert result.stderr.strip() == "ruff: command not found"

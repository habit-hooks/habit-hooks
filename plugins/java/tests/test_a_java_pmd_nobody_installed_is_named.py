"""The tool this plugin does not ship must still answer in one line.

The plugin does not bundle the PMD distribution, so ``pmd`` is the command that
goes missing — and it is spawned from Python, where an absent tool is a
``FileNotFoundError`` and twenty lines of internals would otherwise become the
sensor's diagnosis (#114).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SENSOR = (
    Path(__file__).resolve().parents[1] / "src/habit_hooks_java/sensors/pmd_sensor.py"
)


def test_a_java_pmd_nobody_installed_answers_the_way_a_shell_does(
    tmp_path: Path,
) -> None:
    (tmp_path / "App.java").write_text("class App {}\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SENSOR), "App.java"],
        cwd=tmp_path,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env={"PATH": "/nonexistent"},
    )

    assert result.returncode != 0
    assert result.stdout.strip() == ""
    assert result.stderr.strip() == "pmd: command not found"

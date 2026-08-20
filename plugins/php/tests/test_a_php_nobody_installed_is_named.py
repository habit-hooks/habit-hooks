"""The interpreter this plugin does not ship must still answer in one line.

The plugin bundles ``phpmd.phar`` but nothing to run it with, so ``php`` is the
command that goes missing — and it is spawned from Python, where an absent tool
is a ``FileNotFoundError`` and twenty lines of internals would otherwise become
the sensor's diagnosis (#114).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SENSOR = (
    Path(__file__).resolve().parents[1] / "src/habit_hooks_php/sensors/phpmd_sensor.py"
)


def test_a_php_nobody_installed_answers_the_way_a_shell_does(tmp_path: Path) -> None:
    (tmp_path / "app.php").write_text("<?php\nfunction f($a) { return $a; }\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SENSOR), "app.php"],
        cwd=tmp_path,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env={"PATH": "/nonexistent"},
    )

    assert result.returncode != 0
    assert result.stdout.strip() == ""
    assert result.stderr.strip() == "php: command not found"

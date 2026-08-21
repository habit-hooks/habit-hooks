"""The PHP this run resolved is the one the sensor spawns.

The plugin bundles ``phpmd.phar`` but nothing to run it with, so the sensor
names ``${detector:php}`` and is handed the file this project runs for php as
its first argument. Spawning that file — rather than the bare name it was
resolved from — is the whole of what the sensor owes: a name is looked up again
by the spawn, and Windows' own lookup adds ``.exe`` and nothing else, where a
distribution may have installed php as a shim.

A php nobody installed is no longer answered here. The part carries no file for
it, so nothing is ever spawned and the run answers as it does for any missing
command — the notice, the failed run, and that sensor's dropped findings
(``sensors/broken_part.py``).
"""

from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

from tool_lookup import where_the_bare_name_reaches_nothing

SENSOR = (
    Path(__file__).resolve().parents[1] / "src/habit_hooks_php/sensors/phpmd_sensor.py"
)


def test_the_php_it_is_handed_runs_where_the_name_reaches_nothing(
    php: str, tmp_path: Path
) -> None:
    (tmp_path / "billing.php").write_text(
        "<?php\nfunction charge($a) {\n    $unused = 1;\n    return $a;\n}\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(SENSOR), php, "billing.php"],
        cwd=tmp_path,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=where_the_bare_name_reaches_nothing("php"),
    )

    assert result.returncode == 0, result.stderr
    assert [finding["smell"] for finding in json.loads(result.stdout)] == [
        "unused-variable"
    ]

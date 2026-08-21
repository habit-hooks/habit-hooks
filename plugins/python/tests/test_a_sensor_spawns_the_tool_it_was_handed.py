"""A sensor spawns the tool it was handed, never a name it looks up again.

``sensors/ruff.toml`` and ``sensors/deptry.toml`` each name their tool with
``${detector:<name>}``, so the run resolves it to a file and passes that file as
the helper's first argument. Handing over the file is the whole point: a bare
name is looked up again by whatever spawns it, and Windows' own lookup adds
``.exe`` and nothing else — where a project's venv holds ``deptry.exe`` and npm
installs a Node tool as a ``.cmd`` shim.

A ``PATH`` that cannot answer the tool's own name is what proves the helper
takes it: a helper still spelling that name would find nothing to spawn, while
one handed the file runs a tool no search path leads to.

A tool nobody installed is no longer this plugin's to answer for. The run
resolves the name before the helper is spawned and answers for an absent one
itself, as the ordinary missing command it is
(``tests/test_a_tool_a_part_cannot_run.py``).
"""

from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

from tool_lookup import where_the_bare_name_reaches_nothing

SENSORS = (
    Path(__file__).resolve().parents[1] / "src" / "habit_hooks_python" / "sensors"
)


def _run(
    helper: str, tool: str, project: Path, *arguments: str
) -> subprocess.CompletedProcess[str]:
    """The helper's own run, where nothing answers the tool's bare name."""
    return subprocess.run(
        [sys.executable, str(SENSORS / helper), *arguments],
        cwd=project,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=where_the_bare_name_reaches_nothing(tool),
    )


def test_the_ruff_sensor_spawns_the_ruff_it_was_handed(
    tmp_path: Path, ruff: str
) -> None:
    (tmp_path / "billing.py").write_text("import os\n", encoding="utf-8")

    result = _run("ruff_sensor.py", "ruff", tmp_path, ruff, "billing.py")

    assert result.returncode == 0
    assert result.stderr == ""
    assert [finding["smell"] for finding in json.loads(result.stdout)] == [
        "unused-import"
    ]


def test_the_deptry_sensor_spawns_the_deptry_it_was_handed(
    tmp_path: Path, deptry: str
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.0.0"\ndependencies = ["rich"]\n',
        encoding="utf-8",
    )
    (tmp_path / "app.py").write_text(
        "def fetch(url):\n    return url\n", encoding="utf-8"
    )

    result = _run("deptry_sensor.py", "deptry", tmp_path, deptry)

    assert result.returncode == 0
    assert result.stderr == ""
    assert [finding["smell"] for finding in json.loads(result.stdout)] == [
        "unused-dependency"
    ]

"""A project that declares no dependencies has none that go unused.

deptry raises ``DependencySpecificationNotFoundError`` when it finds no
``pyproject.toml`` carrying a ``[project]``/``[tool.poetry.dependencies]``/
``[tool.pdm]`` section and none of its requirements filenames either — its own
search across PEP 621, poetry, pdm and deptry's configurable requirements
names, in one place, so this sensor recognises that answer rather than
re-implementing the search (see "A wrapped tool's own config wins" in
CLAUDE.md). A project with nothing declared has, honestly, zero declared but
unused dependencies, and that must read as a clean run, not a broken one —
kept distinct here from every other way deptry can fail, which still has to
fail loud (#88).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SENSOR = (
    Path(__file__).resolve().parents[1]
    / "src/habit_hooks_python/sensors/deptry_sensor.py"
)


def test_a_project_declaring_no_dependencies_is_a_clean_run(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("import os\n")

    result = subprocess.run(
        [sys.executable, str(SENSOR)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "[]"
    assert result.stderr.strip() == ""


def test_deptry_still_answers_a_missing_declaration_with_that_error(
    tmp_path: Path,
) -> None:
    """The sensor recognises deptry's exception by name, so a deptry that stops
    raising it must fail here rather than silently retire that branch."""
    (tmp_path / "app.py").write_text("import os\n")

    result = subprocess.run(
        ["deptry", "."],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert "DependencySpecificationNotFoundError" in result.stderr


def test_deptry_failing_another_way_still_fails_the_run(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.0.0"\ndependencies = []\n\n'
        "[tool.deptry]\nnot_a_real_option = true\n"
    )
    (tmp_path / "app.py").write_text("import os\n")

    result = subprocess.run(
        [sys.executable, str(SENSOR)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert result.stdout.strip() == ""
    assert "not_a_real_option" in result.stderr

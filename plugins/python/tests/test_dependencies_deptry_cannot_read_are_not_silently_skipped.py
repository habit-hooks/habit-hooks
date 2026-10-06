
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SENSOR = (
    Path(__file__).resolve().parents[1]
    / "src/habit_hooks_python/sensors/deptry_sensor.py"
)

DECLARATIONS = (
    (
        "setup.py",
        "from setuptools import setup\n\nsetup(name='demo', version='0.0.0')\n",
    ),
    (
        "setup.cfg",
        "[metadata]\nname = demo\nversion = 0.0.0\n\n"
        "[options]\ninstall_requires =\n    attrs\n",
    ),
    ("Pipfile", "[packages]\nattrs = '*'\n"),
)


def _run_sensor(tmp_path: Path, deptry: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SENSOR), deptry],
        cwd=tmp_path,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )


@pytest.mark.parametrize(
    ("declaration", "contents"), DECLARATIONS, ids=[name for name, _ in DECLARATIONS]
)
def test_dependencies_deptry_cannot_read_are_not_silently_skipped(
    tmp_path: Path, deptry: str, declaration: str, contents: str
) -> None:
    (tmp_path / declaration).write_text(contents, encoding="utf-8")
    (tmp_path / "app.py").write_text("import rich\n", encoding="utf-8")

    result = _run_sensor(tmp_path, deptry)

    assert result.returncode == 0
    findings = json.loads(result.stdout)
    assert [finding["smell"] for finding in findings] == ["parse-error"]
    assert [issue["details"]["file"] for issue in findings[0]["issues"]] == [
        declaration
    ]
    assert findings[0]["issues"][0]["details"]["source"] == "deptry:no-declaration"


def test_every_unreadable_declaration_is_named(tmp_path: Path, deptry: str) -> None:
    (tmp_path / "setup.py").write_text(
        "from setuptools import setup\n\nsetup(name='demo', version='0.0.0')\n",
        encoding="utf-8",
    )
    (tmp_path / "Pipfile").write_text("[packages]\nattrs = '*'\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("import rich\n", encoding="utf-8")

    result = _run_sensor(tmp_path, deptry)

    assert result.returncode == 0
    findings = json.loads(result.stdout)
    assert [finding["smell"] for finding in findings] == ["parse-error"]
    assert [issue["details"]["file"] for issue in findings[0]["issues"]] == [
        "setup.py",
        "Pipfile",
    ]

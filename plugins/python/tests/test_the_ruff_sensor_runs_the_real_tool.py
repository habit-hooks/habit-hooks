"""The helper wired to the real ``ruff``, mirroring
``test_a_project_declaring_no_dependencies_is_clean.py``'s real-tool style for
deptry. The pure mapping is covered by
``test_the_ruff_pipeline_maps_codes_to_smells.py``; this proves ruff's own
output still has the shape that mapping expects.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SENSOR = (
    Path(__file__).resolve().parents[1]
    / "src/habit_hooks_python/sensors/ruff_sensor.py"
)


def _run(project: Path, *files: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SENSOR), *files],
        cwd=project,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )


def test_a_clean_file_is_a_clean_run(tmp_path: Path) -> None:
    (tmp_path / "clean.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

    result = _run(tmp_path, "clean.py")

    assert result.returncode == 0
    assert result.stderr == ""
    assert json.loads(result.stdout) == []


def test_a_real_violation_comes_out_as_the_mapped_smell(tmp_path: Path) -> None:
    (tmp_path / "billing.py").write_text(
        "import os\n\n\ndef charge():\n    unused = 1\n    return 0\n",
        encoding="utf-8",
    )

    result = _run(tmp_path, "billing.py")

    assert result.returncode == 0
    findings = json.loads(result.stdout)
    assert {finding["smell"] for finding in findings} == {
        "unused-import",
        "unused-variable",
    }


def test_ruff_maps_a_syntax_error_to_parse_error(tmp_path: Path) -> None:
    (tmp_path / "broken.py").write_text("def broken(:\n    return 1\n", encoding="utf-8")

    result = _run(tmp_path, "broken.py")

    assert result.returncode == 0
    findings = json.loads(result.stdout)
    assert [finding["smell"] for finding in findings] == ["parse-error"]
    assert findings[0]["issues"][0]["details"]["source"] == "ruff:invalid-syntax"

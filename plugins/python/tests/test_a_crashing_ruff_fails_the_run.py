"""A broken ``ruff`` must not read as clean — it must fail the sensor.

``ruff_crashed`` trusts exactly ruff's own contract (0 clean, 1 violations
found); the boundary is exercised directly here, and
``test_a_broken_ruff_toml_fails_the_run`` proves the whole helper honours it
against the real tool, mirroring
``test_deptry_failing_another_way_still_fails_the_run``.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from ruff_sensor import ruff_crashed

SENSOR = (
    Path(__file__).resolve().parents[1]
    / "src/habit_hooks_python/sensors/ruff_sensor.py"
)


def _result(returncode: int) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout="", stderr="")


@pytest.mark.parametrize("returncode", [0, 1])
def test_ruff_s_own_exit_codes_are_trusted(returncode: int) -> None:
    assert ruff_crashed(_result(returncode)) is False


@pytest.mark.parametrize("returncode", [2, 127, -9])
def test_any_other_exit_code_is_a_crash(returncode: int) -> None:
    assert ruff_crashed(_result(returncode)) is True


def test_a_broken_ruff_toml_fails_the_run(tmp_path: Path, ruff: str) -> None:
    (tmp_path / "ruff.toml").write_text(
        "this is not = valid ruff config\n", encoding="utf-8"
    )
    (tmp_path / "app.py").write_text("import os\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SENSOR), ruff, "app.py"],
        cwd=tmp_path,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )

    assert result.returncode == 2
    assert result.stdout.strip() == ""
    assert "ruff.toml" in result.stderr

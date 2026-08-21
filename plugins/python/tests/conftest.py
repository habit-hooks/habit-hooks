"""What every test here needs of the run it stands in for.

**A helper loads as a loose script.** The sensor specs spell
``${python} ${dir}/<helper>.py``, so the interpreter puts the helper's own
directory first on ``sys.path``, and a unit test does the same rather than
reaching the code as ``habit_hooks_python.sensors.ruff_sensor`` — a load path no
run ever takes (see "A plugin helper imports its neighbours as top-level
modules" in CLAUDE.md).

**A helper is handed its tool as a file.** The specs name theirs with
``${detector:<tool>}``, which the run resolves against the project's own bins
before the helper is spawned (``project_paths.tool_executable``). A test
spawning a helper directly stands in for the run, so it asks that same question
and hands over a real file rather than a name. Absent is a failure rather than a
skip: ``uv sync`` brings both, so a machine without one is a suite that has
quietly stopped gating.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

SENSORS = (
    Path(__file__).resolve().parents[1] / "src" / "habit_hooks_python" / "sensors"
)

sys.path.insert(0, str(SENSORS))


@pytest.fixture(scope="session")
def ruff() -> str:
    """The file this machine runs ruff by, as the sensor's first argument."""
    return _installed("ruff")


@pytest.fixture(scope="session")
def deptry() -> str:
    """The file this machine runs deptry by, as the sensor's first argument."""
    return _installed("deptry")


def _installed(tool: str) -> str:
    """The file this machine runs ``tool`` by.

    ``shutil.which`` rather than the name on disk: a console script is
    ``<tool>.exe`` in a Windows venv, which a lookup finds and a spawn handed
    the bare name cannot reach.
    """
    found = shutil.which(tool)
    if found is None:
        pytest.fail(f"{tool} is not on PATH — run 'uv sync'")
    return found

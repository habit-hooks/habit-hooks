"""Load the pmd sensor the way it is actually run, and hand it what a run hands it.

**A helper loads as a loose script.** The sensor spec spells
``${python} ${dir}/pmd_sensor.py``, so the interpreter puts the helper's own
directory first on ``sys.path`` and its neighbour ``pmd_ruleset`` is a plain
top-level import. A unit test here does the same rather than reaching the code as
``habit_hooks_java.sensors.pmd_sensor`` — a load path no run takes, and the only
one that import fails under.

**A helper is handed its tool as a file.** The spec names it with
``${detector:pmd}``, which the run resolves before the helper is spawned
(``project_paths.tool_executable``). A test spawning the helper directly stands
in for the run, so it asks the same question and hands over the same file.
Absent is a failure rather than a skip: CI installs PMD on both legs, so a
machine without it is a suite that has quietly stopped gating.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

SENSORS = Path(__file__).resolve().parents[1] / "src" / "habit_hooks_java" / "sensors"

sys.path.insert(0, str(SENSORS))


@pytest.fixture(scope="session")
def pmd() -> str:
    """The file this machine runs PMD by, as the sensor's first argument.

    ``shutil.which`` rather than the name on disk: PMD ships ``pmd.bat``, which
    Windows finds by a lookup and cannot spawn by the bare name.
    """
    found = shutil.which("pmd")
    if found is None:
        pytest.fail("pmd is not on PATH — 'brew install pmd'")
    return found

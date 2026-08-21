"""What every test here needs of the run it stands in for.

The sensor names the tool it wraps (``${detector:jscpd}`` in
``sensors/jscpd.toml``) and the run resolves that name to a file before the
helper is spawned (``project_paths.tool_executable``). A test that spawns the
helper itself stands in for the run, so it asks the same question and hands over
the same file.

Absent is a failure rather than a skip: CI's ``pnpm install --frozen-lockfile``
brings jscpd, so a machine without it is a suite that has quietly stopped gating
rather than a machine this plugin does not apply to.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

JSCPD_BIN = Path(__file__).resolve().parents[3] / "node_modules" / ".bin"


@pytest.fixture(scope="session")
def jscpd() -> str:
    """The file this machine runs jscpd by, as the sensor's first argument.

    ``shutil.which`` rather than the name on disk: npm installs the tool as a
    ``jscpd.CMD`` shim on Windows, where the extensionless ``jscpd`` beside it
    is a shell script nothing there can spawn.
    """
    found = shutil.which("jscpd", path=str(JSCPD_BIN))
    if found is None:
        pytest.fail("jscpd is not installed — run 'pnpm install' at the repo root")
    return found

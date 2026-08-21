"""What every test here needs of the run it stands in for.

The sensor names the tool it wraps (``${detector:php}`` in
``sensors/phpmd.toml``) and the run resolves that name to a file before the
helper is spawned (``project_paths.tool_executable``). A test that spawns the
helper itself stands in for the run, so it asks the same question and hands over
the same file.

Absent is a failure rather than a skip: both CI runner images ship PHP, so a
machine without it is a suite that has quietly stopped gating rather than a
machine this plugin does not apply to.
"""

from __future__ import annotations

import shutil

import pytest


@pytest.fixture(scope="session")
def php() -> str:
    """The file this machine runs PHP by, as the sensor's first argument.

    ``shutil.which`` rather than the name on disk: a Windows distribution may
    have installed php as a shim, which a lookup finds and a spawn handed the
    bare name cannot reach.
    """
    found = shutil.which("php")
    if found is None:
        pytest.fail("php is not on PATH — 'brew install php'")
    return found

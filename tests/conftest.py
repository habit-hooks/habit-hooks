"""The one installed-wheel install both installed-run modules measure against.

``test_installed_wheel_smoke`` asks whether the core can find its plugins once
packaged and ``test_installed_plugin_packaging`` whether each plugin brought
what its sensors need; both need the same throwaway venv, and building the
wheels twice to answer two halves of one question is a minute of every suite
run. Session-scoped and here rather than imported, because a fixture a module
only names in a signature reads as an unused import wherever it is declared.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from installed_env import build_wheels, install_wheels

# Every distribution this repo releases. A plugin left out of this tuple is a
# plugin whose packaging nothing checks — which is how a Node helper that could
# not resolve its own dependency reached users.
SHIPPED_PACKAGES = (
    "habit-hooks",
    "habit-hooks-generic",
    "habit-hooks-php",
    "habit-hooks-python",
    "habit-hooks-typescript",
)


@pytest.fixture(scope="session")
def installed_habit_sensors(tmp_path_factory) -> Path:
    """``habit-sensors`` as a consumer gets it: installed from built wheels into
    a venv with no source tree, no editable install and no ``plugins/`` sibling
    directory on disk."""
    root = tmp_path_factory.mktemp("wheel-smoke")
    wheels_dir = root / "wheels"
    wheels_dir.mkdir()
    build_wheels(wheels_dir, SHIPPED_PACKAGES)
    return install_wheels(root / "venv", wheels_dir)

"""The fixtures a test module names in a signature rather than importing.

A fixture reads as an unused import wherever it is declared, so every shared one
lives here. Two kinds so far:

* the one installed-wheel install both installed-run modules measure against —
  ``test_installed_wheel_smoke`` asks whether the core can find its plugins once
  packaged and ``test_installed_plugin_packaging`` whether each plugin brought
  what its sensors need; both need the same throwaway venv, and building the
  wheels twice to answer two halves of one question is a minute of every suite
  run;
* the project an ``init`` case asks its question of, whose plugins and whose
  tools are the ones the case wrote rather than whatever this machine has.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from installed_env import build_wheels, install_wheels
from plugin_fixture import write_plugin

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


@pytest.fixture
def init_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A project directory whose only plugin on hand declares nothing.

    ``generic`` is vendored rather than installed so a case's tools are the ones
    it wrote: the generic plugin ``uv sync`` installs declares jscpd, which would
    otherwise be every case's answer. Git's upward walk is stopped above the
    project, so a case that shells out to git can only ever see the repository
    it built — never this checkout.
    """
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    created = tmp_path / "project"
    created.mkdir()
    write_plugin(created, "generic", {"config.toml": ""})
    return created


@pytest.fixture
def toolless_project(init_project: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The same project on an empty ``PATH``: nothing is installed but what the
    case installs, so an answer about a missing tool cannot come from this
    machine happening to have it."""
    empty = init_project.parent / "no-tools"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    return init_project

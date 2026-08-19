"""The fixtures a test module names in a signature rather than importing.

A fixture reads as an unused import wherever it is declared, so every shared one
lives here. Four kinds so far:

* the one installed-wheel install both installed-run modules measure against —
  ``test_installed_wheel_smoke`` asks whether the core can find its plugins once
  packaged and ``test_installed_plugin_packaging`` whether each plugin brought
  what its sensors need; both need the same throwaway venv, and building the
  wheels twice to answer two halves of one question is a minute of every suite
  run;
* the project an ``init`` case asks its question of, whose plugins and whose
  tools are the ones the case wrote rather than whatever this machine has;
* the machine such a case runs on, stripped of the plugins ``uv sync`` installs
  for development, because a case about a plugin nobody has cannot be written on
  a machine that has them all;
* the installation habit-hooks itself is running from, which decides the command
  ``init`` offers for a plugin nobody has — asked by two modules, and written
  out in full, down to the ``pyvenv.cfg``, since otherwise which command that is
  would depend on the machine the suite runs on.
"""

from __future__ import annotations

import sys
from importlib.machinery import ModuleSpec
from pathlib import Path

import pytest
from habit_hooks import plugin_install, resolve
from habit_hooks.plugin_install import UV_TOOL_RECEIPT, VENV_CONFIG
from installed_env import build_wheels, install_wheels
from plugin_fixture import write_plugin

# Every distribution this repo releases. A plugin left out of this tuple is a
# plugin whose packaging nothing checks — which is how a Node helper that could
# not resolve its own dependency reached users.
SHIPPED_PACKAGES = (
    "habit-hooks",
    "habit-hooks-generic",
    "habit-hooks-java",
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
def pluginless_machine(monkeypatch: pytest.MonkeyPatch) -> None:
    """A machine with no habit-hooks plugin installed, whatever this one has.

    ``uv sync`` installs every one of them for development, so the case a plugin
    nobody has is *about* cannot be reached here without saying so: the entry
    points are emptied, leaving whatever the case vendors under
    ``.habit-hooks/`` as the only plugins on hand — which is what a consumer who
    ran ``pip install habit-hooks`` and nothing else has.
    """
    monkeypatch.setattr(resolve, "installed_plugin_dirs", dict)


def _resolving(module: str) -> ModuleSpec:
    """``find_spec`` for an interpreter that has the module asked about."""
    return ModuleSpec(module, loader=None)


def _finding_nothing(module: str) -> None:
    """``find_spec`` for an interpreter that has not."""
    return None


@pytest.fixture
def pip_installed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """habit-hooks running from an environment uv did not install as a tool and
    that has a pip to run: a pip install, a venv, the Homebrew Cellar venv."""
    monkeypatch.setattr(sys, "prefix", str(tmp_path))
    monkeypatch.setattr(plugin_install, "find_spec", _resolving)


@pytest.fixture
def pip_less_prefix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An environment with no pip to answer and no receipt to be known by.

    Every uv-made environment but a tool one looks like this, which is why
    having no pip cannot be what tells them apart: the three below differ only
    in what uv wrote in their ``pyvenv.cfg``, and a case that writes none of it
    is a Python whose environment says nothing about itself at all.
    """
    monkeypatch.setattr(sys, "prefix", str(tmp_path))
    monkeypatch.setattr(plugin_install, "find_spec", _finding_nothing)
    return tmp_path


@pytest.fixture
def uvx_run(pip_less_prefix: Path) -> None:
    """habit-hooks running from `uvx`: an entry in uv's own cache, marked
    relocatable, which uv reuses and prunes as it sees fit."""
    (pip_less_prefix / VENV_CONFIG).write_text("uv = 0.8.11\nrelocatable = true\n")


@pytest.fixture
def uvx_run_with_a_pip(uvx_run: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """The same cache entry, carrying a pip: the crossing that settles which of
    the two questions has to be asked first."""
    monkeypatch.setattr(plugin_install, "find_spec", _resolving)


@pytest.fixture
def uv_run_overlay(pip_less_prefix: Path) -> Path:
    """habit-hooks running under `uv run --with`, which layers a throwaway
    environment of its own over a durable one — and names the one it extends,
    which is the only environment such a run has to install into."""
    extended = pip_less_prefix.parent / "project-venv"
    (pip_less_prefix / VENV_CONFIG).write_text(
        f"uv = 0.8.11\nextends-environment = {extended}\n"
    )
    return extended


@pytest.fixture
def uv_venv(pip_less_prefix: Path) -> None:
    """habit-hooks running from a project's own `uv venv` — a durable
    environment, and the one a project keeps habit-hooks in as a dev
    dependency."""
    (pip_less_prefix / VENV_CONFIG).write_text("uv = 0.8.11\nprompt = project\n")


@pytest.fixture
def uv_tool_installed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """habit-hooks running from `uv tool install`, which leaves its receipt in
    the environment root.

    Written with a pip in reach, which a uv tool environment has not got: it is
    the receipt that has to recognise this one, since what rules pip out here is
    not its absence but the rebuild.
    """
    (tmp_path / UV_TOOL_RECEIPT).write_text("[tool]\n")
    monkeypatch.setattr(sys, "prefix", str(tmp_path))
    monkeypatch.setattr(plugin_install, "find_spec", _resolving)


@pytest.fixture
def toolless_project(init_project: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The same project on an empty ``PATH``: nothing is installed but what the
    case installs, so an answer about a missing tool cannot come from this
    machine happening to have it."""
    empty = init_project.parent / "no-tools"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    return init_project

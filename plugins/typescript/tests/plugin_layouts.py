"""Where an install puts this plugin's files, laid out for real in a temp tree.

Three layouts, because where the package lands decides two different things about
a Node helper. **Under** the project directory — the README's vendoring route
(``.habit-hooks/<plugin>/``) and a project-local ``.venv/`` — the consumer's own
``package.json`` sits above the helpers, so its ``"type"`` reaches them
(``test_node_sensors_ignore_the_project_manifest``). **Outside** it — ``pip``,
``uv tool``, Homebrew — nothing of the project's is above them at all, and a bare
``require`` there resolves against a Python site-packages tree with no
``node_modules`` anywhere in it (``test_the_comment_helper_finds_ts_morph``).

Every layout copies the **whole** package, byte for byte. Byte for byte because a
rewritten copy would prove only that the rewrite works; whole because that is what
vendoring for real means (``docs/habit-hooks-init.spec.md``) and what a sensor has
always needed — the ``.toml`` that names it, the config it falls back to, and the
module beside it that spawns the tool it wraps. ``${dir}`` is the directory the
sensor's ``.toml`` was resolved from, so those files can only ever be found
together anyway.
"""

from __future__ import annotations

import shutil
from pathlib import Path

PACKAGE = Path(__file__).parents[1] / "src" / "habit_hooks_typescript"

# Build leftovers the wheel does not carry, so a copy is what a consumer gets.
NOT_SHIPPED = shutil.ignore_patterns("__pycache__")


def vendored(project: Path) -> Path:
    """The package at the path the README's vendoring route uses."""
    return _copied_to(project / ".habit-hooks" / "typescript")


def in_a_local_venv(project: Path) -> Path:
    """The package at the path `uv pip install` into a project's `.venv/` uses."""
    return _copied_to(
        project
        / ".venv"
        / "lib"
        / "python3.12"
        / "site-packages"
        / "habit_hooks_typescript"
    )


def outside_the_project(root: Path) -> Path:
    """The package where `pip`, `uv tool` and Homebrew put it: a site-packages
    tree of its own, with no `node_modules` anywhere above it."""
    return _copied_to(root / "site-packages" / "habit_hooks_typescript")


def sensor(package: Path, helper: str) -> Path:
    """One of the helpers in an installed package."""
    return package / "sensors" / helper


def _copied_to(destination: Path) -> Path:
    shutil.copytree(PACKAGE, destination, ignore=NOT_SHIPPED, dirs_exist_ok=True)
    return destination

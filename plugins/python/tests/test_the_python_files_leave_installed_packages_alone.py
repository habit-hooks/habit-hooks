"""What this plugin means when it says which files are its language's.

A project that names no ``files`` of its own scans what its plugins declare, and
``habit-hooks init`` writes exactly such a config — so what is declared here *is*
the first run for anyone init set up. A bare ``**/*.py`` reaches into the
project's virtualenv and reports on every installed package, which buries the
project's own findings under thousands that are nobody's to fix.

``site-packages`` is where an installed package lands whatever the environment is
called, so it answers for a ``venv/`` as well as a ``.venv/``.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pathspec

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "habit_hooks_python"

PROJECT_SOURCE = ("src/billing.py", "tests/test_billing.py", "conftest.py")
DEPENDENCIES = (
    ".venv/lib/python3.12/site-packages/attrs/__init__.py",
    "venv/lib/python3.11/site-packages/jinja2/environment.py",
    ".tox/py312/lib/python3.12/site-packages/pytest/__init__.py",
    # Not under site-packages, so only the environment's own name excludes these
    # — and it is spelled both ways about equally often.
    ".venv/bin/activate_this.py",
    "venv/bin/activate_this.py",
)


def _declared_files() -> pathspec.PathSpec:
    config = tomllib.loads((PACKAGE / "config.toml").read_text(encoding="utf-8"))
    return pathspec.PathSpec.from_lines("gitignore", config["files"])


def test_the_project_s_own_python_is_source() -> None:
    spec = _declared_files()

    assert [path for path in PROJECT_SOURCE if spec.match_file(path)] == list(
        PROJECT_SOURCE
    )


def test_an_installed_package_is_not_this_project_s_source() -> None:
    """Under either name a virtualenv usually goes by."""
    spec = _declared_files()

    assert [path for path in DEPENDENCIES if spec.match_file(path)] == []

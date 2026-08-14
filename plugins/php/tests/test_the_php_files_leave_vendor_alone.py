"""What this plugin means when it says which files are its language's.

A project that names no ``files`` of its own scans what its plugins declare, and
``habit-hooks init`` writes exactly such a config — so what is declared here *is*
the first run for anyone init set up. A bare ``**/*.php`` reaches into
``vendor/``, where Composer puts every installed package, and reports on code the
project did not write and cannot change.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pathspec

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "habit_hooks_php"

PROJECT_SOURCE = ("src/Billing.php", "tests/BillingTest.php")
DEPENDENCIES = (
    "vendor/symfony/console/Application.php",
    "vendor/autoload.php",
)


def _declared_files() -> pathspec.PathSpec:
    config = tomllib.loads((PACKAGE / "config.toml").read_text(encoding="utf-8"))
    return pathspec.PathSpec.from_lines("gitignore", config["files"])


def test_the_project_s_own_php_is_source() -> None:
    spec = _declared_files()

    assert [path for path in PROJECT_SOURCE if spec.match_file(path)] == list(
        PROJECT_SOURCE
    )


def test_a_composer_package_is_not_this_project_s_source() -> None:
    spec = _declared_files()

    assert [path for path in DEPENDENCIES if spec.match_file(path)] == []

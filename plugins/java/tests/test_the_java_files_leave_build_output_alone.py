"""What this plugin means when it says which files are its language's.

A project that names no ``files`` of its own scans what its plugins declare, and
``habit-hooks init`` writes exactly such a config — so what is declared here *is*
the first run for anyone init set up. A bare ``**/*.java`` reaches into
``target/``, where Maven puts generated sources, and ``build/``, where Gradle
puts its own — code the project did not write and cannot change.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pathspec

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "habit_hooks_java"

PROJECT_SOURCE = (
    "src/main/java/com/example/Billing.java",
    "src/test/java/com/example/BillingTest.java",
)
BUILD_OUTPUT = (
    "target/generated-sources/annotations/com/example/Generated.java",
    "build/generated/sources/annotationProcessor/java/main/com/example/Generated.java",
)


def _declared_files() -> pathspec.PathSpec:
    config = tomllib.loads((PACKAGE / "config.toml").read_text(encoding="utf-8"))
    return pathspec.PathSpec.from_lines("gitignore", config["files"])


def test_the_project_s_own_java_is_source() -> None:
    spec = _declared_files()

    assert [path for path in PROJECT_SOURCE if spec.match_file(path)] == list(
        PROJECT_SOURCE
    )


def test_generated_build_output_is_not_this_project_s_source() -> None:
    spec = _declared_files()

    assert [path for path in BUILD_OUTPUT if spec.match_file(path)] == []

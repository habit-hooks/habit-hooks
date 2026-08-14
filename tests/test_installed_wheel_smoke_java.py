"""End-to-end smoke test of the java plugin against its installed wheel.

The java sensor reaches for a ruleset it ships when the project names none, so
the bundled ``pmd-ruleset.xml`` must ride along as package data — exactly as the
php case proves for its bundled phar. Building and installing is
``installed_env``; this module is only what an installed run must produce.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from installed_env import (
    build_wheels,
    install_wheels,
    require_pmd,
    run_and_collect_findings,
)


@pytest.fixture(scope="module")
def installed_habit_sensors(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("java-wheel-smoke")
    wheels_dir = root / "wheels"
    wheels_dir.mkdir()
    build_wheels(wheels_dir, ("habit-hooks", "habit-hooks-generic", "habit-hooks-java"))
    return install_wheels(root / "venv", wheels_dir)


def _java_project(tmp_path: Path) -> Path:
    project = tmp_path / "java-proj"
    project.mkdir()
    config = project / ".habit-hooks"
    config.mkdir()
    (config / "config.toml").write_text('plugins = ["java"]\n')
    (project / "Billing.java").write_text(
        "import java.io.File;\n"
        "import java.io.IOException;\n"
        "class Billing {\n"
        "    double charge(double a, double b, double c, double d, double e) {\n"
        "        int dead = 1;\n"
        "        return a + b + c + d + e;\n"
        "    }\n"
        "}\n"
    )
    return project


def test_installed_java_plugin_locates_its_bundled_ruleset(
    installed_habit_sensors: Path, tmp_path: Path
) -> None:
    require_pmd()
    findings = run_and_collect_findings(
        installed_habit_sensors, _java_project(tmp_path)
    )

    by_smell = {finding["smell"]: finding for finding in findings}
    assert by_smell.keys() == {"too-many-parameters", "unused-import", "unused-variable"}
    for finding in findings:
        assert finding["language"] == "java"
        issue = finding["issues"][0]
        assert Path(issue["key"]).name == "Billing.java"
        assert issue["details"]["source"].startswith("pmd:")

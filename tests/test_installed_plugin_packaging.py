"""What each plugin had to carry into its wheel, proved from a real install.

A plugin's sensors lean on things that are not Python: a bundled phar, a Node
helper, a shell pipeline declared in package data. From a checkout every one of
them is reachable by luck of layout, and the failure when it is not is silence —
a sensor that reports nothing reads exactly like a project with nothing wrong.
Both bugs that reached users this week were of that shape, in the one plugin the
installed-wheel gate did not cover.

Every case therefore runs the installed ``habit-sensors`` (``conftest``) against
a project laid out for real (``installed_projects``) and insists a genuine
finding comes back. A machine without the wrapped tool skips: it can say nothing
either way.
"""

from __future__ import annotations

from pathlib import Path

from installed_env import require_tool, run_and_collect_findings
from installed_projects import (
    JAVA_SOURCE,
    PHP_SOURCE,
    PYTHON_SOURCE,
    TYPESCRIPT_SOURCE,
    java_project,
    php_project,
    python_project,
    typescript_project,
)


def _sole_issue(findings: list[dict], smell: str) -> dict:
    """The one issue the sensor under test is the only thing that can report."""
    assert [finding["smell"] for finding in findings] == [smell], findings
    issues = findings[0]["issues"]
    assert len(issues) == 1, issues
    return issues[0]


def test_installed_php_plugin_locates_its_bundled_phar(
    installed_habit_sensors: Path, tmp_path: Path
) -> None:
    """phpmd ships inside the wheel, so the sensor has to find it beside itself
    with no source tree on disk."""
    require_tool("php")
    project = php_project(tmp_path)

    findings = run_and_collect_findings(installed_habit_sensors, project)

    by_smell = {finding["smell"]: finding for finding in findings}
    assert by_smell.keys() == {"too-many-parameters", "unused-variable"}
    for finding in findings:
        assert finding["language"] == "php"
        issue = finding["issues"][0]
        assert Path(issue["key"]).name == PHP_SOURCE
        assert issue["details"]["source"].startswith("phpmd:")


def test_installed_java_plugin_locates_its_bundled_ruleset(
    installed_habit_sensors: Path, tmp_path: Path
) -> None:
    """The pmd sensor reaches for the ruleset it ships when the project names
    none, so the bundled ``pmd-ruleset.xml`` must ride along as package data
    with no source tree on disk to fall back on."""
    require_tool("pmd")
    project = java_project(tmp_path)

    findings = run_and_collect_findings(installed_habit_sensors, project)

    by_smell = {finding["smell"]: finding for finding in findings}
    assert by_smell.keys() == {
        "too-many-parameters",
        "unused-import",
        "unused-variable",
    }
    for finding in findings:
        assert finding["language"] == "java"
        issue = finding["issues"][0]
        assert Path(issue["key"]).name == JAVA_SOURCE
        assert issue["details"]["source"].startswith("pmd:")


def test_installed_typescript_plugin_resolves_ts_morph_from_the_project(
    installed_habit_sensors: Path, tmp_path: Path
) -> None:
    """The comment sensor's Node helper must both ship as package data and reach
    the project's ts-morph. Installed, that helper sits in a site-packages tree
    with no ``node_modules`` anywhere above it, so a bare ``require`` died on its
    first line for every consumer while this repository's own runs passed —
    something above the helper here happened to have ts-morph in it."""
    require_tool("node")
    project = typescript_project(tmp_path)

    issue = _sole_issue(
        run_and_collect_findings(installed_habit_sensors, project),
        "non-essential-comment",
    )

    assert issue["key"] == TYPESCRIPT_SOURCE
    assert issue["details"]["file"] == TYPESCRIPT_SOURCE
    assert issue["details"]["source"] == "comment:non-essential"


def test_installed_python_plugin_runs_its_ruff_pipeline(
    installed_habit_sensors: Path, tmp_path: Path
) -> None:
    """The ruff sensor is a shell pipeline rather than a helper script, so what
    packaging can lose here is the sensor spec itself — and a lost sensor is a
    smell nobody is ever told about."""
    require_tool("ruff")
    require_tool("jq")
    project = python_project(tmp_path)

    issue = _sole_issue(
        run_and_collect_findings(installed_habit_sensors, project),
        "unused-variable",
    )

    assert issue["key"] == PYTHON_SOURCE
    assert issue["details"]["source"] == "ruff:F841"

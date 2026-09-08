"""Unused private-member detection remains PMD's decision."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SENSOR = (
    Path(__file__).resolve().parents[1] / "src/habit_hooks_java/sensors/pmd_sensor.py"
)
RULESET_HEADER = """<?xml version="1.0"?>
<ruleset name="custom" xmlns="http://pmd.sourceforge.net/ruleset/2.0.0"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
 xsi:schemaLocation="http://pmd.sourceforge.net/ruleset/2.0.0 https://pmd.sourceforge.io/ruleset_2_0_0.xsd">
 <description>project policy</description>
"""


def _run(project: Path, pmd: str, *arguments: str) -> list[dict]:
    result = subprocess.run(
        [sys.executable, str(SENSOR), pmd, *arguments, "--", "Members.java"],
        cwd=project,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_the_bundled_rules_report_only_unreferenced_private_members(
    tmp_path: Path, pmd: str
) -> None:
    (tmp_path / "Members.java").write_text(
        "class Members {\n"
        "    private int staleField = 1;\n"
        "    private int liveField = 2;\n"
        "    private void staleMethod() {}\n"
        "    private int liveMethod() { return liveField; }\n"
        "    int value() { return liveMethod(); }\n"
        "}\n",
        encoding="utf-8",
    )

    findings = _run(tmp_path, pmd)

    assert [finding["smell"] for finding in findings] == ["unused-class-member"]
    issues = findings[0]["issues"]
    assert [issue["details"]["line"] for issue in issues] == [2, 4]
    assert [issue["details"]["message"] for issue in issues] == [
        "Avoid unused private fields such as 'staleField'.",
        "Avoid unused private methods such as 'staleMethod()'.",
    ]
    assert [issue["details"]["source"] for issue in issues] == [
        "pmd:UnusedPrivateField",
        "pmd:UnusedPrivateMethod",
    ]
    assert all(Path(issue["key"]).name == "Members.java" for issue in issues)
    assert all("name" not in issue["details"] for issue in issues)


def test_the_bundled_rules_leave_framework_and_serialization_exclusions_to_pmd(
    tmp_path: Path, pmd: str
) -> None:
    (tmp_path / "Members.java").write_text(
        "@interface Managed {}\n"
        "class Members implements java.io.Serializable {\n"
        "    private static final long serialVersionUID = 1L;\n"
        "    @Managed private Object injected;\n"
        "    private Object staleField;\n"
        "    private void readObject(java.io.ObjectInputStream stream)\n"
        "            throws java.io.IOException, ClassNotFoundException {\n"
        "        stream.defaultReadObject();\n"
        "    }\n"
        "    private void staleMethod() {}\n"
        "}\n",
        encoding="utf-8",
    )

    findings = _run(tmp_path, pmd)

    assert [finding["smell"] for finding in findings] == ["unused-class-member"]
    issues = findings[0]["issues"]
    assert [issue["details"]["line"] for issue in issues] == [5, 10]
    assert [issue["details"]["source"] for issue in issues] == [
        "pmd:UnusedPrivateField",
        "pmd:UnusedPrivateMethod",
    ]
    messages = [issue["details"]["message"] for issue in issues]
    assert all("serialVersionUID" not in message for message in messages)
    assert all("injected" not in message for message in messages)
    assert all("readObject" not in message for message in messages)


def test_a_project_ruleset_decides_whether_unused_members_are_enabled(
    tmp_path: Path, pmd: str
) -> None:
    (tmp_path / "Members.java").write_text(
        "class Members {\n"
        "    private int staleField;\n"
        "    private void staleMethod() {}\n"
        "}\n",
        encoding="utf-8",
    )
    ruleset = tmp_path / "ruleset.xml"
    ruleset.write_text(
        RULESET_HEADER
        + ' <rule ref="category/java/design.xml/AvoidDeeplyNestedIfStmts"/>\n'
        + "</ruleset>\n",
        encoding="utf-8",
    )

    omitted = _run(tmp_path, pmd)

    assert omitted == []

    ruleset.write_text(
        RULESET_HEADER
        + ' <rule ref="category/java/bestpractices.xml/UnusedPrivateField"/>\n'
        + ' <rule ref="category/java/bestpractices.xml/UnusedPrivateMethod"/>\n'
        + "</ruleset>\n",
        encoding="utf-8",
    )

    enabled = _run(tmp_path, pmd)

    assert [issue["details"]["source"] for issue in enabled[0]["issues"]] == [
        "pmd:UnusedPrivateField",
        "pmd:UnusedPrivateMethod",
    ]


def test_a_project_ruleset_can_customize_pmds_ignored_field_names(
    tmp_path: Path, pmd: str
) -> None:
    (tmp_path / "Members.java").write_text(
        "class Members {\n"
        "    private int retainedByPolicy;\n"
        "    private int staleField;\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "ruleset.xml").write_text(
        RULESET_HEADER
        + ' <rule ref="category/java/bestpractices.xml/UnusedPrivateField">\n'
        + "  <properties>\n"
        + '   <property name="ignoredFieldNames" value="retainedByPolicy"/>\n'
        + "  </properties>\n"
        + " </rule>\n"
        + "</ruleset>\n",
        encoding="utf-8",
    )

    findings = _run(tmp_path, pmd)

    issues = findings[0]["issues"]
    assert [issue["details"]["line"] for issue in issues] == [3]
    assert issues[0]["details"]["message"] == (
        "Avoid unused private fields such as 'staleField'."
    )

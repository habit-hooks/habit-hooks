"""The bundled PMD fallback pins behavior that PMD's defaults must not move."""

from __future__ import annotations

import xml.etree.ElementTree as ElementTree
from pathlib import Path

RULESET = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "habit_hooks_java"
    / "sensors"
    / "pmd-ruleset.xml"
)
PMD_NAMESPACE = {"pmd": "http://pmd.sourceforge.net/ruleset/2.0.0"}
DEEP_NESTING_RULE = "category/java/design.xml/AvoidDeeplyNestedIfStmts"


def test_the_bundled_ruleset_explicitly_reports_the_third_nested_if() -> None:
    root = ElementTree.parse(RULESET).getroot()

    rules = [
        rule
        for rule in root.findall("pmd:rule", PMD_NAMESPACE)
        if rule.get("ref") == DEEP_NESTING_RULE
    ]

    assert len(rules) == 1
    problem_depth = rules[0].findall(
        "pmd:properties/pmd:property[@name='problemDepth']", PMD_NAMESPACE
    )
    assert len(problem_depth) == 1
    assert problem_depth[0].get("value") == "3"

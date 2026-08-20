"""``findings()`` reproduces the old ``ruff | jq`` pipeline exactly: map each
violation's ``code`` to a smell, group by smell (alphabetically, as jq's
``group_by`` sorts), and shape each group into the canonical finding.

These exercise the pure mapping logic with synthetic ruff-JSON-shaped entries
— the same style ``plugins/java/tests/test_class_level_metric_violations_are_dropped.py``
uses for ``pmd_sensor.findings`` — rather than spawning the real tool, which
``test_the_ruff_sensor_runs_the_real_tool.py`` does instead.
"""

from __future__ import annotations

import subprocess

import pytest
from ruff_sensor import CODE_SMELLS, findings, violations


def _entry(code: str, filename: str = "a.py", row: int = 1) -> dict:
    return {
        "code": code,
        "filename": filename,
        "location": {"row": row, "column": 1},
        "message": "m",
    }


def test_zero_entries_is_no_findings() -> None:
    assert findings([]) == []


def test_one_entry_becomes_one_finding_with_one_issue() -> None:
    entry = {
        "code": "F401",
        "filename": "a.py",
        "location": {"row": 3, "column": 8},
        "message": "`os` unused",
    }

    assert findings([entry]) == [
        {
            "smell": "unused-import",
            "details": {},
            "issues": [
                {
                    "key": "a.py",
                    "details": {
                        "file": "a.py",
                        "line": 3,
                        "column": 8,
                        "message": "`os` unused",
                        "source": "ruff:F401",
                    },
                }
            ],
        }
    ]


def test_many_entries_group_by_smell_sorted_alphabetically() -> None:
    """Insertion order is deliberately the reverse of the alphabetical group
    order jq's ``group_by`` produces, so a test that merely preserved input
    order would still pass unless the sort is checked."""
    unused_variable = _entry("F841", filename="b.py")
    high_complexity = _entry("C901", filename="a.py")

    result = findings([unused_variable, high_complexity])

    assert [finding["smell"] for finding in result] == [
        "high-complexity",
        "unused-variable",
    ]


def test_two_issues_for_the_same_smell_share_one_finding() -> None:
    first = _entry("F401", filename="a.py", row=1)
    second = _entry("F401", filename="a.py", row=2)

    result = findings([first, second])

    assert len(result) == 1
    assert [issue["details"]["line"] for issue in result[0]["issues"]] == [1, 2]


@pytest.mark.parametrize("code", sorted(CODE_SMELLS))
def test_every_mapped_code_reaches_its_own_smell(code: str) -> None:
    result = findings([_entry(code)])

    assert [finding["smell"] for finding in result] == [CODE_SMELLS[code]]
    assert result[0]["issues"][0]["details"]["source"] == f"ruff:{code}"


def test_a_code_with_no_smell_mapped_is_dropped_not_crashed() -> None:
    """A code outside the plugin's vocabulary has no guide and no catalogue
    severity, so it is dropped rather than forwarded under ruff's own name —
    see "A sensor emits vocabulary smells only" in CLAUDE.md. Indexing a dict
    with ``.get`` rather than jq's ``{...}[.code]`` is what makes this safe by
    construction instead of a crash (issue #83)."""
    mapped = _entry("F401", filename="a.py")
    unmapped = _entry("PLR9999", filename="b.py")

    assert findings([unmapped]) == []
    assert [f["smell"] for f in findings([mapped, unmapped])] == ["unused-import"]


def test_empty_stdout_is_no_findings() -> None:
    result = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

    assert violations(result) == []

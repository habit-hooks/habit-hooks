from __future__ import annotations

import json
from pathlib import Path

import pytest

from slow_test import DEFAULT_BUDGET_SECONDS, findings, positive_seconds, report_entries
from slow_test_report import Timings, matches_test_pattern
from types import SimpleNamespace


def test_the_default_budget_is_one_second():
    assert DEFAULT_BUDGET_SECONDS == 1.0


@pytest.mark.parametrize("budget", ["0", "-1", "nan", "inf", "-inf", "nonsense"])
def test_invalid_budgets_are_rejected(budget):
    import argparse

    with pytest.raises(argparse.ArgumentTypeError, match="positive number"):
        positive_seconds(budget)


def test_unrounded_timings_decide_the_budget_not_display_precision():
    assert findings([("tests/test_a.py::test_at", 1.0)], 1.0) == []
    issue = findings([("tests/test_a.py::test_over", 1.00001)], 1.0)[0]["issues"][0]
    assert issue["details"]["duration"] == 1.00001


def test_slow_tests_are_ordered_slowest_first():
    report = findings([("a.py::test_a", 1.5), ("a.py::test_b", 2.0)], 1.0)
    assert [issue["key"] for issue in report[0]["issues"]] == [
        "a.py::test_b",
        "a.py::test_a",
    ]


@pytest.mark.parametrize(
    ("path", "counted"),
    [
        ("tests/test_billing.py", True),
        ("tests/billing_test.py", True),
        ("conftest.py", False),
        ("billing.py", False),
    ],
)
def test_default_pytest_patterns_are_respected(path, counted):
    assert matches_test_pattern(path, ["test_*.py", "*_test.py"]) is counted


def test_custom_pytest_patterns_are_respected():
    assert matches_test_pattern("specs/billing_spec.py", ["*_spec.py"])
    assert not matches_test_pattern("tests/test_old.py", ["*_spec.py"])


def test_windows_file_paths_are_normalized_without_changing_param_ids():
    nodeid = r"tests\test_a.py::test_a[C:\users\u1234]"
    issue = findings([(nodeid, 1.5)], 1.0)[0]["issues"][0]
    assert issue["key"] == nodeid
    assert issue["details"]["file"] == "tests/test_a.py"


def test_attempts_sum_phases_but_repeats_do_not_inflate_a_test():
    timings = Timings(None)
    for duration, phase in [(0.1, "setup"), (0.6, "call"), (0.1, "teardown")] * 2:
        timings.pytest_runtest_logreport(
            SimpleNamespace(
                nodeid="a.py::test_a",
                duration=duration,
                when=phase,
            )
        )
    assert timings.durations["a.py::test_a"] == pytest.approx(0.8)


def test_missing_executions_are_not_a_complete_report(tmp_path: Path):
    report = tmp_path / "timings.json"
    report.write_text(
        json.dumps({"collected": 1, "durations": {}, "collection_failed": False}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        report_entries(report)


@pytest.mark.parametrize("code", [0, 1, 2, 3, 4, 5])
def test_missing_structured_output_is_never_a_clean_run(tmp_path, capsys, code):
    import subprocess
    from slow_test import report_from

    result = subprocess.CompletedProcess([], code, "fake timing output", "")
    assert report_from(result, tmp_path / "missing.json", 1.0) == 2
    assert capsys.readouterr().out == ""

"""Unit tests for the guards around the anchoring boundary.

The spec cases cover what a well-formed sensor gets. These cover the two things
they cannot reach: the spellings under which a key and its file are the same
path, and what a *malformed* sensor must get instead of a traceback out of the
runner — this boundary reads output from tools nobody here wrote.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from habit_hooks.sensors.finding_paths import aliasing_notices, anchored
from habit_hooks.sensors.model import SensorError


def _finding(*issues: object) -> list[dict]:
    return [{"smell": "oversized-file", "details": {}, "issues": list(issues)}]


def _anchored_issues(findings: list[dict], project_dir: Path) -> list[dict]:
    return anchored(findings, project_dir, "alpha")[0]["issues"]


def test_a_key_spelled_differently_from_its_file_is_still_that_file(
    tmp_path: Path,
) -> None:
    findings = _finding({"key": "./src/a.py", "details": {"file": "src/a.py"}})

    assert _anchored_issues(findings, tmp_path)[0]["key"] == "src/a.py"


def test_an_absolute_key_beside_a_relative_file_is_still_that_file(
    tmp_path: Path,
) -> None:
    key = str(tmp_path / "src" / "a.py")
    findings = _finding({"key": key, "details": {"file": "src/a.py"}})

    assert _anchored_issues(findings, tmp_path)[0]["key"] == "src/a.py"


def test_a_key_that_names_no_file_is_still_left_alone(tmp_path: Path) -> None:
    """The carve-out survives: `deptry` keys by module, `knip` by export name."""
    findings = _finding({"key": "requests", "details": {"file": "pyproject.toml"}})

    assert _anchored_issues(findings, tmp_path)[0]["key"] == "requests"


def test_a_key_spelling_cannot_hide_an_alias(tmp_path: Path) -> None:
    findings = _finding(
        {"key": "./index.ts", "details": {"file": "index.ts"}},
        {"key": "./index.ts", "details": {"file": "ui/src/index.ts"}},
    )

    notices = aliasing_notices(anchored(findings, tmp_path, "alpha"), "alpha")

    assert notices == [
        "sensor 'alpha' keys 2 files as 'index.ts' (index.ts, ui/src/index.ts)"
        " — snoozing it would exempt them all"
    ]


def test_details_that_is_not_an_object_fails_by_name(tmp_path: Path) -> None:
    findings = _finding({"key": "src/a.py", "details": None})

    with pytest.raises(SensorError, match="'alpha'"):
        anchored(findings, tmp_path, "alpha")


def test_an_issue_that_is_not_an_object_fails_by_name(tmp_path: Path) -> None:
    with pytest.raises(SensorError, match="'alpha'"):
        anchored(_finding("src/a.py"), tmp_path, "alpha")


@pytest.mark.parametrize("issues", [{"key": "a.py"}, "src/a.py", 5])
def test_issues_that_is_not_a_list_fails_by_name(
    issues: object, tmp_path: Path
) -> None:
    """Including the shapes that are not even iterable — a `for` over one of
    those is a `TypeError` nobody catches."""
    findings = [{"smell": "oversized-file", "details": {}, "issues": issues}]

    with pytest.raises(SensorError, match="'alpha'"):
        anchored(findings, tmp_path, "alpha")

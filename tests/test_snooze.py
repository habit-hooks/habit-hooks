"""Unit tests for the snooze transform's rules, with git out of the picture.

The executable spec ([habit-snooze.spec.md]) covers the command; these pin the
two pieces the spec cannot show directly — which file an issue is anchored to,
and what a lapsed file does to the drop decision.
"""

from __future__ import annotations

from habit_hooks.snooze import anchor_file, transform

_FINDING = {
    "smell": "oversized-file",
    "details": {"maxAllowed": 200},
    "issues": [
        {"key": "src/x.ts", "details": {"file": "src/x.ts"}},
        {"key": "requests", "details": {"file": "src/y.py"}},
    ],
}


def test_anchor_prefers_the_details_file() -> None:
    issue = {"key": "requests", "details": {"file": "src/y.py"}}
    assert anchor_file(issue) == "src/y.py"


def test_anchor_falls_back_to_the_key_without_a_file() -> None:
    assert anchor_file({"key": "src/x.ts", "details": {"line": 3}}) == "src/x.ts"


def test_anchor_falls_back_to_the_key_without_details() -> None:
    assert anchor_file({"key": "src/x.ts"}) == "src/x.ts"


def test_no_lapsed_file_drops_every_snoozed_issue() -> None:
    kept = transform([_FINDING], {"src/x.ts", "requests"})
    assert kept == []


def test_a_lapsed_file_resurfaces_only_its_own_issue() -> None:
    kept = transform([_FINDING], {"src/x.ts", "requests"}, {"src/y.py"})
    assert [issue["key"] for issue in kept[0]["issues"]] == ["requests"]


def test_a_lapsed_file_leaves_unsnoozed_issues_alone() -> None:
    kept = transform([_FINDING], set(), {"src/y.py"})
    assert [issue["key"] for issue in kept[0]["issues"]] == ["src/x.ts", "requests"]


def test_a_finding_without_issues_passes_through() -> None:
    empty = {"smell": "duplicated-code", "details": {}, "issues": []}
    assert transform([empty], {"src/x.ts"}, {"src/x.ts"}) == [empty]

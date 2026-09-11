"""The terms a snooze is decided in: which key, and which file.

Which key an issue is filed under, and which file that key is anchored to, is
neither the transform and its CLI (``snooze.py``) nor the index file itself
(``snooze_index.py``), and both sides need the answer. The module is named for
what these terms serve: the rule that decides whether a snooze still holds.
"""

from __future__ import annotations


def finding_keys(findings: list[dict]) -> list[str]:
    return [issue["key"] for finding in findings for issue in finding["issues"]]


def anchor_file(issue: dict) -> str:
    """The file an issue's snooze is anchored to: its ``details.file``, else its key.

    A sensor keys an issue by whatever groups it best — a module or export name,
    not always a path — so the file to compare comes from the details bag.
    """
    return issue.get("details", {}).get("file", issue["key"])


def snoozed_anchors(findings: list[dict], snoozed: set[str]) -> set[str]:
    """The files the snoozed issues sit in — where a lapse could apply."""
    return {
        anchor_file(issue)
        for finding in findings
        for issue in finding["issues"]
        if issue["key"] in snoozed
    }

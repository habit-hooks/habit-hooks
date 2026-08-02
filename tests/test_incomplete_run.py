"""The reserved ``incomplete-run`` finding the sensors stage raises against itself.

A failed sensor or transformer contributes no findings, so without this the
mapper would see ``[]`` and render the clean guide over broken tooling (#88). The
builder turns each failure notice into an issue the mapper can coach.
"""

from __future__ import annotations

from habit_hooks.catalogue import INCOMPLETE_RUN
from habit_hooks.sensors import incomplete_run_finding


def test_each_notice_becomes_a_coachable_issue() -> None:
    notices = [
        "habit-sensors: sensor 'comment' failed: boom",
        "habit-sensors: transformer 'snooze' failed: exit 1",
    ]

    finding = incomplete_run_finding(notices)

    assert finding["smell"] == INCOMPLETE_RUN
    assert [issue["details"]["content"] for issue in finding["issues"]] == notices
    # The key carries the notice so the shape stays a well-formed finding.
    assert [issue["key"] for issue in finding["issues"]] == notices


def test_no_notices_yields_no_issues() -> None:
    finding = incomplete_run_finding([])

    assert finding["smell"] == INCOMPLETE_RUN
    assert finding["issues"] == []

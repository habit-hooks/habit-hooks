"""Which issues survive a merge: what makes two of them one observation (#140).

An issue is identified by its ``key`` and **the place it names**, and by nothing
either tool said in its own voice — ``source`` and ``message`` disagree between
two sensors precisely because they are two tools. Every field of that place is
load-bearing, and each case below fails if its own is dropped from
``PLACE_FIELDS``.

Which findings are merged in the first place is
``test_merging_findings_of_one_smell.py``'s subject, and why a *single*
finding's issues are never touched is
``test_a_sensors_own_issues_are_never_second_guessed.py``'s.
"""

from __future__ import annotations

from habit_hooks.merged_findings import merged

ONE_GUIDE = "guides/the-one.md"


def _same_guide(finding: dict) -> str:
    return ONE_GUIDE


def _finding(smell: str, issues: list[dict], **rest: object) -> dict:
    return {"smell": smell, "details": {}, "issues": issues, **rest}


def _at(file: str, **details: object) -> dict:
    return {"key": file, "details": {"file": file, **details}}


def test_two_sensors_naming_one_place_leave_one_issue() -> None:
    """Neither sensor's own words count towards the identity — they disagree on
    ``source`` and ``message`` precisely because they are two tools."""
    findings = [
        _finding("oversized-file", [_at("src/a.py", source="eslint:max-lines")]),
        _finding("oversized-file", [_at("src/a.py", lines=260, source="line-count")]),
    ]

    assert merged(findings, _same_guide)[0]["issues"] == [
        _at("src/a.py", source="eslint:max-lines")
    ]


def test_a_line_nobody_stated_is_absent_rather_than_a_value() -> None:
    """One sensor spells the absence ``null`` and the other omits the key. Both
    mean the same place, and an identity built by stringifying would read the
    first as ``'None'`` and keep them apart."""
    findings = [
        _finding("oversized-file", [_at("src/a.py", line=None, column=None)]),
        _finding("oversized-file", [_at("src/a.py")]),
    ]

    assert len(merged(findings, _same_guide)[0]["issues"]) == 1


def test_one_key_found_in_two_files_is_two_issues() -> None:
    """``deptry`` keys by module and ``knip`` by export name, so a key says
    nothing about where — one ``default`` export per file is two things to
    delete."""
    findings = [
        _finding("unused-export", [{"key": "default", "details": {"file": "src/a.ts"}}]),
        _finding("unused-export", [{"key": "default", "details": {"file": "src/b.ts"}}]),
    ]

    assert len(merged(findings, _same_guide)[0]["issues"]) == 2


def test_two_clones_starting_in_different_places_are_two_duplications() -> None:
    """A jscpd occurrence names a range rather than a line, and every other fact
    about two clones of one file is identical."""
    findings = [
        _finding("duplicated-code", [_at("src/a.py", startLine=10, endLine=30)]),
        _finding("duplicated-code", [_at("src/a.py", startLine=100, endLine=30)]),
    ]

    assert len(merged(findings, _same_guide)[0]["issues"]) == 2


def test_two_clones_of_different_lengths_are_two_duplications() -> None:
    """One block duplicated elsewhere in full and elsewhere again in part starts
    at the same line twice; only where it ends tells the two apart."""
    findings = [
        _finding("duplicated-code", [_at("src/a.py", startLine=10, endLine=30)]),
        _finding("duplicated-code", [_at("src/a.py", startLine=10, endLine=90)]),
    ]

    assert len(merged(findings, _same_guide)[0]["issues"]) == 2


def test_two_findings_on_one_line_at_different_columns_are_two_issues() -> None:
    """Two ``any``s on one line are two things to fix, and eslint keys both by
    the file — the column is the only thing telling them apart."""
    findings = [
        _finding("explicit-any", [_at("src/a.ts", line=5, column=11)]),
        _finding("explicit-any", [_at("src/a.ts", line=5, column=30)]),
    ]

    assert len(merged(findings, _same_guide)[0]["issues"]) == 2


def test_an_issue_that_states_no_details_at_all_still_reports() -> None:
    """``details`` is conventional, not required — a sensor may key an issue and
    say nothing else about it."""
    findings = [
        _finding("unused-dependency", [{"key": "requests"}]),
        _finding("unused-dependency", [{"key": "urllib3"}]),
    ]

    assert [issue["key"] for issue in merged(findings, _same_guide)[0]["issues"]] == [
        "requests",
        "urllib3",
    ]


def test_two_places_in_one_file_are_two_issues() -> None:
    """A project's own sensor emitting a catalogued smell merges with the
    shipped one's finding (docs/authoring-plugins.spec.md), and both key an
    issue by its file — so two complex functions in that file are told apart by
    their line and nothing else."""
    findings = [
        _finding("high-complexity", [_at("src/a.py", line=12)]),
        _finding("high-complexity", [_at("src/a.py", line=88)]),
    ]

    assert len(merged(findings, _same_guide)[0]["issues"]) == 2


def test_a_third_finding_is_weighed_against_the_second_as_well_as_the_first() -> None:
    """Everything already gathered is what a later finding is checked against,
    not the first finding alone. Here only the second and third name one file,
    and counting it twice tells the reader to fix something already listed."""
    findings = [
        _finding("oversized-file", [_at("src/a.py", source="eslint:max-lines")]),
        _finding("oversized-file", [_at("src/b.py", source="line-count")]),
        _finding("oversized-file", [_at("src/b.py", source="ours")]),
    ]

    issues = merged(findings, _same_guide)[0]["issues"]

    assert [issue["key"] for issue in issues] == ["src/a.py", "src/b.py"]

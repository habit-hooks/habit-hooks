"""Which findings become one finding, and what the merged one says (#140).

Which of their *issues* survive is ``test_which_issues_survive_a_merge.py``'s
subject; what a reader sees is ``test_a_smell_is_coached_once.py``'s.

``merged`` is handed the question "which guide would this finding render" rather
than answering it, so these cases answer it themselves — the mapper answers it
with ``rendering.resolve_guide``.
"""

from __future__ import annotations

from habit_hooks.merged_findings import merged

ONE_GUIDE = "guides/the-one.md"


def _same_guide(finding: dict) -> str:
    return ONE_GUIDE


def _guide_of_its_language(finding: dict) -> str:
    """What the real resolution does for a smell two plugins both coach: the
    language picks the plugin, and the plugin picks the file."""
    return f"{finding.get('language')}/{finding['smell']}.md"


def _finding(smell: str, issues: list[dict], **rest: object) -> dict:
    return {"smell": smell, "details": {}, "issues": issues, **rest}


def _at(file: str, **details: object) -> dict:
    return {"key": file, "details": {"file": file, **details}}


def test_no_findings_merge_into_no_findings() -> None:
    assert merged([], _same_guide) == []


def test_one_finding_comes_back_as_it_was() -> None:
    finding = _finding("oversized-file", [_at("src/a.py")], language="python")

    assert merged([finding], _same_guide) == [finding]


def test_merging_leaves_the_findings_it_was_handed_alone() -> None:
    """``merged`` answers a question about the findings it is given; a merge
    that edited them would make a sensor's own output depend on having been
    rendered."""
    finding = _finding("oversized-file", [_at("src/a.py")])

    merged([finding, _finding("oversized-file", [_at("src/b.py")])], _same_guide)

    assert finding["issues"] == [_at("src/a.py")]


def test_a_smell_arriving_three_times_is_one_finding() -> None:
    """jscpd emits a finding per clone, so a run of any size arrives this way."""
    findings = [_finding("duplicated-code", [_at(f"src/{n}.py")]) for n in "abc"]

    assert len(merged(findings, _same_guide)) == 1


def test_issues_keep_the_order_they_arrived_in() -> None:
    findings = [
        _finding("oversized-file", [_at("src/a.py"), _at("src/b.py")]),
        _finding("oversized-file", [_at("src/c.py")]),
    ]

    issues = merged(findings, _same_guide)[0]["issues"]

    assert [issue["key"] for issue in issues] == ["src/a.py", "src/b.py", "src/c.py"]


def test_one_smell_coached_by_two_plugins_stays_two_findings() -> None:
    """A polyglot repo's `high-complexity` routes to the python plugin's guide
    for a `.py` file and to generic's for a `.ts` one. Merged on the smell alone,
    whichever arrived first would coach both — a TypeScript file explained in
    Python."""
    findings = [
        _finding("high-complexity", [_at("src/a.py", line=12)], language="python"),
        _finding("high-complexity", [_at("src/b.ts", line=40)], language="typescript"),
    ]

    assert len(merged(findings, _guide_of_its_language)) == 2


def test_two_smells_sharing_one_guide_keep_their_own_banners() -> None:
    """A ``[smells.<name>] guide`` override can point two smells at one file, and
    the banner names the smell — so the guide alone cannot be the key."""
    findings = [
        _finding("oversized-file", [_at("src/a.py")]),
        _finding("high-complexity", [_at("src/a.py")]),
    ]

    assert [f["smell"] for f in merged(findings, _same_guide)] == [
        "oversized-file",
        "high-complexity",
    ]


def test_a_fact_only_one_finding_stated_survives() -> None:
    """``line-count`` states the threshold it enforced and eslint does not, so a
    guide rendering ``details.maxAllowed`` needs the merge to keep it."""
    findings = [
        _finding("oversized-file", [_at("src/a.py")]),
        {
            "smell": "oversized-file",
            "details": {"maxAllowed": 200},
            "issues": [_at("src/b.py")],
        },
    ]

    assert merged(findings, _same_guide)[0]["details"] == {"maxAllowed": 200}


def test_a_fact_two_findings_disagree_about_is_dropped() -> None:
    """jscpd's ``lines`` describes one clone pair. Three pairs in one finding
    have no single answer, and publishing the first pair's as the whole
    finding's would teach the reader a wrong number — where a missing key
    renders as nothing at all."""
    findings = [
        {"smell": "duplicated-code", "details": {"lines": 21}, "issues": []},
        {"smell": "duplicated-code", "details": {"lines": 40}, "issues": []},
    ]

    assert merged(findings, _same_guide)[0]["details"] == {}


def test_a_language_the_first_finding_did_not_carry_is_taken_from_the_next() -> None:
    """The runner stamps ``language`` from the producing plugin, and ``generic``
    declares none — so the languageless finding is often the one that arrives
    first."""
    findings = [
        _finding("oversized-file", [_at("src/a.ts")]),
        _finding("oversized-file", [_at("src/b.ts")], language="typescript"),
    ]

    assert merged(findings, _same_guide)[0]["language"] == "typescript"


def test_the_first_finding_to_name_a_top_level_value_keeps_it() -> None:
    """First non-null, not last — the merged ``language`` is re-read when the
    guide renders, so the answer has to be one of the group's own."""
    findings = [
        _finding("oversized-file", [_at("src/a.py")], language="python"),
        _finding("oversized-file", [_at("src/b.ts")], language="typescript"),
    ]

    assert merged(findings, _same_guide)[0]["language"] == "python"


def test_a_fact_restated_after_a_contradiction_stays_dropped() -> None:
    """jscpd states ``lines`` per clone pair, so three pairs of 21, 40 and 21
    lines is ordinary. Once two findings have disagreed the key has no answer,
    and a third agreeing with the first must not put the first one back — that
    is the wrong number this exists to keep out, arriving one finding later."""
    findings = [
        {"smell": "duplicated-code", "details": {"lines": 21}, "issues": []},
        {"smell": "duplicated-code", "details": {"lines": 40}, "issues": []},
        {"smell": "duplicated-code", "details": {"lines": 21}, "issues": []},
    ]

    assert merged(findings, _same_guide)[0]["details"] == {}

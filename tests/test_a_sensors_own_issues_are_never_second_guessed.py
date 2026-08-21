"""A sensor's own issue list survives the merge exactly as it arrived.

#140 is about two *sensors* reporting one observation, so deduplication happens
only when a later finding is folded into an earlier one. Within a single
finding nothing is dropped: the sensor meant what it emitted, and three shipped
sensors (``pmd``, ``phpmd``, ``comment``) key an issue by its file, give a line,
and give no column — so two of their issues on one line are indistinguishable to
any identity the merge can build from the place alone. Only the tool's
``message`` tells them apart, and that is deliberately not part of the identity
(two tools describing one thing disagree about exactly that).

``knip`` used to be a fourth. It now translates knip's ``col`` into the
``column`` the contract names, and keys by export name, so its issues are told
apart by the place rule and it is no longer a witness for this one.

Each case below is the shape its sensor really produces; the comment names the
function that builds it.
"""

from __future__ import annotations

from habit_hooks.merged_findings import merged

ONE_GUIDE = "guides/the-one.md"


def _same_guide(finding: dict) -> str:
    return ONE_GUIDE


def _kept_issues(smell: str, issues: list[dict]) -> list[dict]:
    finding = {"smell": smell, "details": {}, "issues": issues}
    return merged([finding], _same_guide)[0]["issues"]


def test_two_java_variables_declared_on_one_line_are_two_issues() -> None:
    """``int a = 1, b = 2;`` is two unused locals at one place.
    ``pmd_sensor.issue`` keys by file and carries ``beginline``, no column."""
    issues = [
        {
            "key": "src/Order.java",
            "details": {
                "file": "src/Order.java",
                "line": 12,
                "message": "Avoid unused local variables such as 'a'.",
                "source": "pmd:UnusedLocalVariable",
            },
        },
        {
            "key": "src/Order.java",
            "details": {
                "file": "src/Order.java",
                "line": 12,
                "message": "Avoid unused local variables such as 'b'.",
                "source": "pmd:UnusedLocalVariable",
            },
        },
    ]

    assert len(_kept_issues("unused-variable", issues)) == 2


def test_two_php_variables_assigned_on_one_line_are_two_issues() -> None:
    """``$a = 1; $b = 2;`` likewise. ``phpmd_sensor.issue`` keys by file and
    carries ``beginLine``, no column."""
    issues = [
        {
            "key": "src/Order.php",
            "details": {
                "file": "src/Order.php",
                "line": 8,
                "message": "Avoid unused local variables such as '$a'.",
                "source": "phpmd:UnusedLocalVariable",
            },
        },
        {
            "key": "src/Order.php",
            "details": {
                "file": "src/Order.php",
                "line": 8,
                "message": "Avoid unused local variables such as '$b'.",
                "source": "phpmd:UnusedLocalVariable",
            },
        },
    ]

    assert len(_kept_issues("unused-variable", issues)) == 2


def test_a_block_and_a_line_comment_on_one_line_are_two_issues() -> None:
    """``foo(/* legacy */ x); // remove me`` is two comments to judge.
    ``comment.cjs``'s ``issue`` keys by file and carries a line, no column."""
    issues = [
        {
            "key": "src/a.ts",
            "details": {
                "file": "src/a.ts",
                "line": 4,
                "message": 'block-line comment: "/* legacy */"',
                "source": "comment:non-essential",
            },
        },
        {
            "key": "src/a.ts",
            "details": {
                "file": "src/a.ts",
                "line": 4,
                "message": 'single-line comment: "// remove me"',
                "source": "comment:non-essential",
            },
        },
    ]

    assert len(_kept_issues("non-essential-comment", issues)) == 2


def test_a_later_findings_own_repeated_place_survives_too() -> None:
    """The rule is not "the first finding is authoritative" — every finding's
    own list is. A second sensor's two variables on one line both stand, and
    only what an *earlier* finding already named is dropped."""
    already_named = {
        "key": "src/Order.java",
        "details": {"file": "src/Order.java", "line": 5, "source": "pmd:UnusedLocalVariable"},
    }
    on_one_line = [
        {
            "key": "src/Order.java",
            "details": {"file": "src/Order.java", "line": 12, "message": "'a'"},
        },
        {
            "key": "src/Order.java",
            "details": {"file": "src/Order.java", "line": 12, "message": "'b'"},
        },
    ]
    findings = [
        {"smell": "unused-variable", "details": {}, "issues": [already_named]},
        {"smell": "unused-variable", "details": {}, "issues": on_one_line},
    ]

    assert len(merged(findings, _same_guide)[0]["issues"]) == 3

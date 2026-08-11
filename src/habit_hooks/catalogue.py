"""The canonical smell catalogue (docs/smell-vocabulary.md): default severities."""

from __future__ import annotations

ENFORCED = "enforced"
SUGGESTED = "suggested"

# The reserved smell a run raises against itself when a sensor or transformer
# broke: it turns "the run did not complete" into a finding on the pipe, so the
# mapper coaches it and never renders the clean guide over broken tooling (#88).
INCOMPLETE_RUN = "incomplete-run"

DEFAULT_SEVERITY: dict[str, str] = {
    "oversized-function": ENFORCED,
    "too-many-parameters": ENFORCED,
    "high-complexity": ENFORCED,
    "deep-nesting": ENFORCED,
    "oversized-file": ENFORCED,
    "unused-variable": ENFORCED,
    "loose-equality": ENFORCED,
    "var-declaration": ENFORCED,
    "non-const-binding": ENFORCED,
    "duplicate-import": ENFORCED,
    "warning-comment": SUGGESTED,
    "explicit-any": SUGGESTED,
    "non-null-assertion": SUGGESTED,
    "redundant-type-annotation": ENFORCED,
    "non-essential-comment": SUGGESTED,
    "duplicated-code": SUGGESTED,
    "unused-class-member": ENFORCED,
    "unused-file": ENFORCED,
    "unused-export": ENFORCED,
    "test-only-dead-code": ENFORCED,
    "unused-dependency": ENFORCED,
    "unused-import": ENFORCED,
    "swallowed-exception": SUGGESTED,
    "parse-error": ENFORCED,
    INCOMPLETE_RUN: ENFORCED,
}

UNCOACHED_GUIDE = "uncoached.md"

# What a run does with a smell this catalogue does not name — the root
# ``uncoached`` config key (#111). The catalogue is the record of what has been
# decided worth failing a build over, so a name absent from it has had no such
# decision made about it and coaches without blocking by default.
UNCOACHED_SUGGEST = "suggest"
UNCOACHED_IGNORE = "ignore"
UNCOACHED_ENFORCE = "enforce"
UNCOACHED_POLICIES = (UNCOACHED_SUGGEST, UNCOACHED_IGNORE, UNCOACHED_ENFORCE)


def incomplete_run_finding(notices: list[str]) -> dict:
    """The reserved-smell finding a failed run carries on the pipe.

    Each notice becomes an issue the mapper coaches through
    ``guides/incomplete-run.md``. It lives here, beside the smell it names,
    because both stages raise it: the sensors stage for a broken sensor or
    transformer, the mapper for a stage that died before writing anything.
    """
    return {
        "smell": INCOMPLETE_RUN,
        "details": {},
        "issues": [
            {"key": notice, "details": {"content": notice}} for notice in notices
        ],
    }

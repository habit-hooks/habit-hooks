from __future__ import annotations

ENFORCED = "enforced"
SUGGESTED = "suggested"

INCOMPLETE_RUN = "incomplete-run"

DEFAULT_SEVERITY: dict[str, str] = {
    "oversized-function": ENFORCED,
    "too-many-parameters": ENFORCED,
    "high-complexity": ENFORCED,
    "deep-nesting": ENFORCED,
    "oversized-file": ENFORCED,
    "oversized-block": ENFORCED,
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
    "slow-test": SUGGESTED,
    "parse-error": ENFORCED,
    INCOMPLETE_RUN: ENFORCED,
}

UNCOACHED_GUIDE = "uncoached.md"

UNCOACHED_SUGGEST = "suggest"
UNCOACHED_IGNORE = "ignore"
UNCOACHED_ENFORCE = "enforce"
UNCOACHED_POLICIES = (UNCOACHED_SUGGEST, UNCOACHED_IGNORE, UNCOACHED_ENFORCE)


def incomplete_run_finding(notices: list[str]) -> dict:
    return {
        "smell": INCOMPLETE_RUN,
        "details": {},
        "issues": [
            {"key": notice, "details": {"content": notice}} for notice in notices
        ],
    }

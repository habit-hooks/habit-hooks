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

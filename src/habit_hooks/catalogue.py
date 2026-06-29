"""The canonical smell catalogue (docs/smell-vocabulary.md): default severities."""

from __future__ import annotations

ENFORCED = "enforced"
SUGGESTED = "suggested"

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
    "unused-dependency": ENFORCED,
    "unused-import": ENFORCED,
    "swallowed-exception": SUGGESTED,
    "parse-error": ENFORCED,
}

UNCOACHED_GUIDE = "uncoached.md"

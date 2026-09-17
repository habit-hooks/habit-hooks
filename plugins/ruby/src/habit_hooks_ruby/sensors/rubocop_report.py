"""RuboCop's JSON report, parsed and shaped into the canonical findings.

RuboCop's own JSON nests offences under each file; this flattens them, groups by
smell and shapes each into the canonical finding.

**An unmapped cop is forwarded, not dropped**, which is the opposite of the knip
sensor and the same as the eslint one. CLAUDE.md's test for a wrapped tool is
"whose vocabulary is it?" Knip's key set is knip's own, but a cop that fired is
one the project's ``.rubocop.yml`` turned on, so forwarding it saves running
RuboCop separately. Its smell key is the cop name verbatim
(``Style/StringLiterals``). A ``/`` in a smell key is already precedented by
eslint forwarding ``@typescript-eslint/no-explicit-any``. Nothing downstream
breaks on one. An uncatalogued smell renders through ``uncoached.md``, and the
root ``uncoached`` key (default ``suggest``) decides whether it fails the run.

``Metrics/ClassLength`` and ``Metrics/ModuleLength`` are the two cops
deliberately left uncoached: they measure a class or module, and the vocabulary
has no class-scoped smell for them to back. Like every unmapped cop they are
forwarded under their own names and rendered through ``uncoached.md``,
``suggest`` until a class and module scoped coach exists.

The three complexity cops share one smell on purpose. They are correlated but
independent. A method tripping two cops keeps both measurements inside a single coaching
block.

``Metrics/BlockLength`` maps to its own smell rather than to
``oversized-function``: a block is an anonymous function the project never
named, and its coaching (name the work as a method, let the declaration point
at it) differs enough from a method's to warrant the ruby plugin's own guide.
"""

from __future__ import annotations

import json
import subprocess

COP_SMELLS = {
    "Metrics/ParameterLists": "too-many-parameters",
    "Metrics/MethodLength": "oversized-function",
    "Metrics/BlockLength": "oversized-block",
    "RSpec/MultipleExpectations": "multiple-expectations",
    "Metrics/CyclomaticComplexity": "high-complexity",
    "Metrics/PerceivedComplexity": "high-complexity",
    "Metrics/AbcSize": "high-complexity",
    "Metrics/BlockNesting": "deep-nesting",
    "Lint/UselessAssignment": "unused-variable",
    "Lint/SuppressedException": "swallowed-exception",
    "Lint/Syntax": "parse-error",
}


def report(result: subprocess.CompletedProcess[str]) -> dict | None:
    """RuboCop's JSON report, or ``None`` where it produced none.

    ``files`` has to be there, not merely valid JSON. That key is what makes it
    a report rather than something else that happens to parse.
    """
    text = result.stdout.strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) and "files" in parsed else None


def offenses(parsed: dict) -> list[dict]:
    """RuboCop's per-file nesting flattened, each offence carrying its path."""
    return [
        {"file": entry["path"], "offense": offense}
        for entry in parsed.get("files", [])
        for offense in entry["offenses"]
    ]


def smell_of(cop_name: str) -> str:
    """This plugin's smell for a cop, or the cop itself where it has none.

    ``.get`` with the cop as its own default, never a bare lookup. The string
    comes from RuboCop and nothing constrains it to the table above (issue #83).
    """
    return COP_SMELLS.get(cop_name, cop_name)


def issue(entry: dict) -> dict:
    offense = entry["offense"]
    return {
        "key": entry["file"],
        "details": {
            "file": entry["file"],
            "line": offense["location"]["line"],
            "column": offense["location"]["column"],
            "message": offense["message"],
            "source": "rubocop:" + offense["cop_name"],
        },
    }


def findings(entries: list[dict]) -> list[dict]:
    by_smell: dict[str, list[dict]] = {}
    for entry in entries:
        by_smell.setdefault(smell_of(entry["offense"]["cop_name"]), []).append(entry)
    return [
        {
            "smell": smell,
            "details": {},
            "issues": [issue(entry) for entry in by_smell[smell]],
        }
        for smell in sorted(by_smell)
    ]

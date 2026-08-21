"""Run ruff and print canonical findings, mapped from rule code to smell.

ruff's own JSON is one entry per violation; this groups them by mapped smell
and shapes each into the canonical finding — the job the old
``ruff | jq`` pipeline did, without needing ``jq`` installed (dropping the
plugin's only other declared detector, and the shell it took to pipe through
it).

An entry's ``code`` not in :data:`CODE_SMELLS` has no smell to report it
under (a code outside ``--select`` besides ``invalid-syntax``, which ruff
reports regardless of ``--select``). It is dropped rather than crashed on or
forwarded under ruff's own name — the same choice the knip sensor makes for a
key with no smell mapped (see "A sensor emits vocabulary smells only" in
CLAUDE.md): a key nobody catalogued has no guide and no severity, so
forwarding it can only fail a run and decline to explain why. Dropping is
also safe *by construction* rather than by ``--select`` pinning the set, which
is what the old jq filter depended on (indexing a jq object with a key that
maps to nothing is a jq crash, not a miss — issue #83).
"""

from __future__ import annotations

import json
import subprocess
import sys

SELECTED_CODES = "C901,PLR0913,PLR0915,F841,F401,BLE001"

CODE_SMELLS = {
    "C901": "high-complexity",
    "PLR0913": "too-many-parameters",
    "PLR0915": "oversized-function",
    "F841": "unused-variable",
    "F401": "unused-import",
    "BLE001": "swallowed-exception",
    "invalid-syntax": "parse-error",
}

# ruff's own contract: 0 is clean, 1 is "violations found" — both trustworthy.
# Anything else is ruff never having produced a real report (bad config, a
# missing file, an internal error), the same distinction part_output.py's
# TOOL_EXIT_CODES draws for a part run directly.
TOOL_EXIT_CODES = (0, 1)


def run_ruff(ruff: str, files: list[str]) -> subprocess.CompletedProcess[str]:
    """What ruff said, spawned as the file this sensor was handed for it.

    ``sensors/ruff.toml`` names ``${detector:ruff}``, so the run resolves ruff
    to a file before this helper starts and passes it as the first argument —
    the ``ruff.exe`` a bare ``["ruff", ...]`` spawn misses on Windows. A ruff
    nobody installed never reaches here at all: the run answers for it as the
    missing command it is, in one line rather than a traceback (#114).
    """
    return subprocess.run(
        [ruff, "check", "--output-format=json", f"--select={SELECTED_CODES}", *files],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )


def ruff_crashed(result: subprocess.CompletedProcess[str]) -> bool:
    return result.returncode not in TOOL_EXIT_CODES


def violations(result: subprocess.CompletedProcess[str]) -> list[dict]:
    text = result.stdout.strip()
    return json.loads(text) if text else []


def issue(entry: dict) -> dict:
    return {
        "key": entry["filename"],
        "details": {
            "file": entry["filename"],
            "line": entry["location"]["row"],
            "column": entry["location"]["column"],
            "message": entry["message"],
            "source": "ruff:" + entry["code"],
        },
    }


def findings(entries: list[dict]) -> list[dict]:
    by_smell: dict[str, list[dict]] = {}
    for entry in entries:
        smell = CODE_SMELLS.get(entry["code"])
        if smell is None:
            continue
        by_smell.setdefault(smell, []).append(entry)
    return [
        {
            "smell": smell,
            "details": {},
            "issues": [issue(entry) for entry in by_smell[smell]],
        }
        for smell in sorted(by_smell)
    ]


def main() -> int:
    ruff = sys.argv[1]
    files = sys.argv[2:]
    result = run_ruff(ruff, files)
    if ruff_crashed(result):
        sys.stderr.write(result.stderr)
        return 2
    print(json.dumps(findings(violations(result))))
    return 0


if __name__ == "__main__":
    sys.exit(main())

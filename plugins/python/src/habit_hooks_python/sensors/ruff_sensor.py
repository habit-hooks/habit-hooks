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

from tool_spawn import run_tool

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


def run_ruff(files: list[str]) -> subprocess.CompletedProcess[str]:
    """What ruff said, or what a shell says about a ruff nobody installed.

    ``pip install habit-hooks-python`` brings neither wrapped tool with it, so
    this is the ordinary state of a machine that has just enabled the plugin —
    and an absent tool raised a ``FileNotFoundError`` out of here, making
    twenty lines of Python internals the sensor's diagnosis (#114). This
    wrapper is what looks for ruff, so it answers the way the shell would
    have, and that phrase is what the run recognises to name the missing
    tool. Looking is ``tool_spawn``'s, which names the file — ``ruff.exe`` or
    a ``.cmd`` shim on Windows, neither of which a bare ``["ruff", ...]``
    spawn reliably reaches there.
    """
    command = [
        "ruff",
        "check",
        "--output-format=json",
        f"--select={SELECTED_CODES}",
        *files,
    ]
    try:
        return run_tool(command)
    except FileNotFoundError:
        return subprocess.CompletedProcess(
            command, 127, "", "ruff: command not found\n"
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
    files = sys.argv[1:]
    result = run_ruff(files)
    if ruff_crashed(result):
        sys.stderr.write(result.stderr)
        return 2
    print(json.dumps(findings(violations(result))))
    return 0


if __name__ == "__main__":
    sys.exit(main())

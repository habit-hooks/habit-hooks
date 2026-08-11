"""Run PHPMD and print canonical smell findings.

PHPMD exits 2 when it finds violations and 1 on a real error, so a bare pipe
cannot tell a clean run from a crash. This wrapper runs PHPMD against the scoped
files, treats only 0/2 as success, and shapes each rule into the canonical
finding, mapping PHPMD rule names to smell keys.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

RULE_SMELLS = {
    "ExcessiveParameterList": "too-many-parameters",
    "CyclomaticComplexity": "high-complexity",
    "ExcessiveMethodLength": "oversized-function",
    "UnusedLocalVariable": "unused-variable",
}

RULESETS = "codesize,unusedcode"
SUCCESS_EXIT_CODES = (0, 2)


def run_phpmd(files: list[str]) -> subprocess.CompletedProcess[str]:
    """What PHPMD said, or what a shell says about a PHP nobody installed.

    The plugin ships the phar but not the interpreter, so ``php`` is the command
    that goes missing — and an absent one raised a ``FileNotFoundError`` out of
    here, making twenty lines of Python internals the sensor's diagnosis (#114).
    This wrapper is what looks for php, so it answers the way the shell would
    have, and that phrase is what the run recognises to name the missing tool.
    """
    phar = str(Path(__file__).with_name("phpmd.phar"))
    command = [
        "php",
        "-d",
        "error_reporting=0",
        "-d",
        "display_errors=0",
        phar,
        ",".join(files),
        "json",
        RULESETS,
    ]
    try:
        return subprocess.run(command, capture_output=True, text=True)
    except FileNotFoundError:
        return subprocess.CompletedProcess(command, 127, "", "php: command not found\n")


def violations(report: dict) -> list[dict]:
    return [
        {"file": file["file"], "violation": violation}
        for file in report.get("files", [])
        for violation in file["violations"]
    ]


def issue(entry: dict) -> dict:
    violation = entry["violation"]
    return {
        "key": entry["file"],
        "details": {
            "file": entry["file"],
            "line": violation["beginLine"],
            "message": violation["description"],
            "source": "phpmd:" + violation["rule"],
        },
    }


def findings(entries: list[dict]) -> list[dict]:
    by_smell: dict[str, list[dict]] = {}
    for entry in entries:
        smell = RULE_SMELLS.get(entry["violation"]["rule"])
        if smell is not None:
            by_smell.setdefault(smell, []).append(issue(entry))
    return [
        {"smell": smell, "details": {}, "issues": issues}
        for smell, issues in by_smell.items()
    ]


def main() -> int:
    files = sys.argv[1:]
    if not files:
        print("[]")
        return 0
    result = run_phpmd(files)
    if result.returncode not in SUCCESS_EXIT_CODES:
        sys.stderr.write(result.stderr or result.stdout)
        return 2
    report = json.loads(result.stdout)
    print(json.dumps(findings(violations(report))))
    return 0


if __name__ == "__main__":
    sys.exit(main())

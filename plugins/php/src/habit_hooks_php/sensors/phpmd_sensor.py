"""Run PHPMD and print canonical smell findings.

PHPMD exits 2 when it finds violations and 1 on a real error, so a bare pipe
cannot tell a clean run from a crash. This wrapper runs PHPMD against the scoped
files, treats only 0/2 as success, and shapes each rule into the canonical
finding, mapping PHPMD rule names to smell keys.

The plugin ships the phar but not the interpreter, so the sensor names
``${detector:php}`` and its ``sys.argv[1]`` is the file this project runs for
php — the scoped files follow it. A php nobody installed never reaches here at
all: the part has no file for it, so the run answers with the missing-command
notice before anything is spawned.
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


def run_phpmd(php: str, files: list[str]) -> subprocess.CompletedProcess[str]:
    """What PHPMD said, run by the ``php`` this project was handed.

    The file rather than the name: a name would be looked up again by the spawn,
    and Windows' own lookup adds ``.exe`` and nothing else, where a distribution
    may have installed php as a shim. PHP's own error reporting is silenced so
    its deprecation notices cannot leak onto the JSON the phar prints.
    """
    phar = str(Path(__file__).with_name("phpmd.phar"))
    return subprocess.run(
        [
            php,
            "-d",
            "error_reporting=0",
            "-d",
            "display_errors=0",
            phar,
            ",".join(files),
            "json",
            RULESETS,
        ],
        capture_output=True,
        encoding="utf-8",
        errors="replace",  # sensors.spawn's policy
    )


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
    php, files = sys.argv[1], sys.argv[2:]
    if not files:
        print("[]")
        return 0
    result = run_phpmd(php, files)
    if result.returncode not in SUCCESS_EXIT_CODES:
        sys.stderr.write(result.stderr or result.stdout)
        return 2
    report = json.loads(result.stdout)
    print(json.dumps(findings(violations(report))))
    return 0


if __name__ == "__main__":
    sys.exit(main())

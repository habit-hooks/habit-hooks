"""Run deptry and print ``unused-dependency`` findings.

deptry's stdout is unreliable when piped, so this wrapper runs it against a temp
JSON report, reads that report, and shapes each ``DEP002`` (a declared but unused
dependency) into the canonical finding.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def run_deptry(report: Path) -> subprocess.CompletedProcess[str]:
    """What deptry said, or what a shell says about a deptry nobody installed.

    ``pip install habit-hooks-python`` brings neither detector with it, so this
    is the ordinary state of a machine that has just enabled the plugin — and an
    absent tool raised a ``FileNotFoundError`` out of here, making twenty lines
    of Python internals the sensor's diagnosis (#114). This wrapper is what looks
    for deptry, so it answers the way the shell would have, and that phrase is
    what the run recognises to name the missing tool.
    """
    command = ["deptry", ".", "--json-output", str(report)]
    try:
        return subprocess.run(
            command,
            capture_output=True,
            encoding="utf-8",
            errors="replace",  # sensors.spawn's policy
        )
    except FileNotFoundError:
        return subprocess.CompletedProcess(
            command, 127, "", "deptry: command not found\n"
        )


def deptry_crashed(result: subprocess.CompletedProcess[str], report: Path) -> bool:
    return result.returncode not in (0, 1) or not report.is_file()


def deptry_found_no_declaration(result: subprocess.CompletedProcess[str]) -> bool:
    """Whether deptry crashed because it found no dependency declaration to check.

    deptry raises ``DependencySpecificationNotFoundError`` when it finds no
    dependency declaration to check. Asking the tool this way, instead of
    reimplementing its PEP 621/poetry/pdm search, keeps the answer from
    drifting off deptry's own. A project with none declared genuinely has
    zero declared-but-unused dependencies — a clean result, not a swallowed
    failure (#88). Matching on the exception's class name, only inside the
    already-crashed branch, keeps every other crash failing loud.
    """
    return "DependencySpecificationNotFoundError" in result.stderr


def unused_dependencies(report: Path) -> list[dict]:
    entries = json.loads(report.read_text(encoding="utf-8"))
    return [entry for entry in entries if entry["error"]["code"] == "DEP002"]


def issue(entry: dict) -> dict:
    return {
        "key": entry["module"],
        "details": {
            "module": entry["module"],
            "file": entry["location"]["file"],
            "message": entry["error"]["message"],
            "source": "deptry:DEP002",
        },
    }


def findings(entries: list[dict]) -> list[dict]:
    if not entries:
        return []
    return [
        {
            "smell": "unused-dependency",
            "details": {},
            "issues": [issue(entry) for entry in entries],
        }
    ]


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "deptry-report.json"
        result = run_deptry(report)
        if deptry_crashed(result, report):
            if deptry_found_no_declaration(result):
                print(json.dumps([]))
                return 0
            sys.stderr.write(result.stderr)
            return 2
        print(json.dumps(findings(unused_dependencies(report))))
    return 0


if __name__ == "__main__":
    sys.exit(main())

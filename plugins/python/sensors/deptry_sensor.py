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
    return subprocess.run(
        ["deptry", ".", "--json-output", str(report)],
        capture_output=True,
        text=True,
    )


def deptry_crashed(result: subprocess.CompletedProcess[str], report: Path) -> bool:
    return result.returncode not in (0, 1) or not report.is_file()


def unused_dependencies(report: Path) -> list[dict]:
    entries = json.loads(report.read_text())
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
            sys.stderr.write(result.stderr)
            return 2
        print(json.dumps(findings(unused_dependencies(report))))
    return 0


if __name__ == "__main__":
    sys.exit(main())

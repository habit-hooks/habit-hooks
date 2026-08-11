"""Run the jscpd CLI and print ``duplicated-code`` findings.

jscpd writes its result to a report file rather than stdout, and exits non-zero
when duplication crosses its configured threshold. This wrapper runs it against a
temp report, reads that report regardless of the exit code, and shapes each clone
into a finding.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    return parser.parse_args(argv)


def scan_paths(config: str) -> list[str]:
    return json.loads(Path(config).read_text())["path"]


def run_jscpd(
    paths: list[str], config: str, output: Path
) -> subprocess.CompletedProcess[str]:
    """What jscpd said, or what a shell says about a jscpd nobody installed.

    An absent tool raised a ``FileNotFoundError`` out of here and twenty lines of
    Python internals became the sensor's diagnosis (#114). This wrapper is what
    looks for jscpd, so it answers the way the shell would have — and that phrase
    is what the run recognises to name the missing tool.
    """
    command = ["jscpd", "--reporters", "json", "--output", str(output), "--config", config]
    try:
        return subprocess.run([*command, *paths], capture_output=True, text=True)
    except FileNotFoundError:
        return subprocess.CompletedProcess(command, 127, "", "jscpd: command not found\n")


def occurrence(side: dict) -> dict:
    return {
        "key": side["name"],
        "details": {
            "file": side["name"],
            "startLine": side["start"],
            "endLine": side["end"],
            "source": "jscpd:duplication",
        },
    }


def clone_finding(clone: dict) -> dict:
    return {
        "smell": "duplicated-code",
        "details": {"lines": clone["lines"], "tokens": clone["tokens"]},
        "issues": [occurrence(clone["firstFile"]), occurrence(clone["secondFile"])],
    }


def findings(report: Path) -> list[dict]:
    if not report.is_file():
        return []
    clones = json.loads(report.read_text())["duplicates"]
    return [clone_finding(clone) for clone in clones]


def main(argv: list[str] | None = None) -> int:
    """Print the findings, or fail the way the tool did.

    Neither signal jscpd gives is conclusive alone, so both are read:

    - **exit 0, no report** — it scanned and found no clones. jscpd only writes a
      report when it has duplicates to put in it, so this is the ordinary clean
      case and must stay clean.
    - **exit 0, report** — clones under the configured threshold.
    - **non-zero, report** — duplication crossed the threshold. A real result;
      the report is read regardless of the exit code.
    - **non-zero, no report** — jscpd itself broke. Saying ``[]`` here would be
      this wrapper promising a clean run on behalf of a tool that never
      delivered one, so its complaint is forwarded and the sensor fails.
    """
    args = parse_args(argv if argv is not None else sys.argv[1:])
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp)
        result = run_jscpd(scan_paths(args.config), args.config, output)
        report = output / "jscpd-report.json"
        if result.returncode != 0 and not report.is_file():
            sys.stderr.write(result.stderr or result.stdout)
            return 1
        print(json.dumps(findings(report)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

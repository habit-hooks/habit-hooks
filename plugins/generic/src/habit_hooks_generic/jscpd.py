from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

JSCPD_CONFIG = ".jscpd.json"
PACKAGE_JSON = "package.json"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("jscpd")
    parser.add_argument("--fallback-config", required=True)
    return parser.parse_args(argv)


def manifest_of(project: Path) -> dict:
    manifest = project / PACKAGE_JSON
    if not manifest.is_file():
        return {}
    try:
        content = json.loads(manifest.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return content if isinstance(content, dict) else {}


def project_configures_jscpd(project: Path) -> bool:
    if (project / JSCPD_CONFIG).is_file():
        return True
    return bool(manifest_of(project).get("jscpd"))


def config_arguments(fallback: str, project: Path) -> list[str]:
    project_path = [project.as_posix()]
    if project_configures_jscpd(project):
        return project_path
    return ["--config", fallback, *project_path]


def run_jscpd(
    jscpd: str, arguments: list[str], output: Path
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [jscpd, "--reporters", "json", "--output", str(output), *arguments],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )


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


MISSING_REPORT = "jscpd wrote no report: it scanned nothing\n"


def findings(report: Path) -> list[dict]:
    clones = json.loads(report.read_text(encoding="utf-8"))["duplicates"]
    return [clone_finding(clone) for clone in clones]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    arguments = config_arguments(args.fallback_config, Path.cwd())
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp)
        result = run_jscpd(args.jscpd, arguments, output)
        report = output / "jscpd-report.json"
        if not report.is_file():
            sys.stderr.write(result.stderr if result.returncode != 0 else MISSING_REPORT)
            return 1
        print(json.dumps(findings(report)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

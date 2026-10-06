
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

UNREADABLE_DECLARATION_NAMES = ("setup.py", "setup.cfg", "Pipfile")


def run_deptry(deptry: str, report: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [deptry, ".", "--json-output", str(report)],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )


def deptry_crashed(result: subprocess.CompletedProcess[str], report: Path) -> bool:
    return result.returncode not in (0, 1) or not report.is_file()


def deptry_found_no_declaration(result: subprocess.CompletedProcess[str]) -> bool:
    return "DependencySpecificationNotFoundError" in result.stderr


def unreadable_declarations() -> list[Path]:
    return [
        Path(name) for name in UNREADABLE_DECLARATION_NAMES if Path(name).is_file()
    ]


def unchecked_dependencies(declarations: list[Path]) -> list[dict]:
    return [
        {
            "smell": "parse-error",
            "details": {},
            "issues": [
                {
                    "key": str(declaration),
                    "details": {
                        "file": str(declaration),
                        "message": (
                            f"dependencies declared in {declaration} are never "
                            "checked — deptry reads pyproject.toml or requirements "
                            "files only"
                        ),
                        "source": "deptry:no-declaration",
                    },
                }
                for declaration in declarations
            ],
        }
    ]


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
    deptry = sys.argv[1]
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "deptry-report.json"
        result = run_deptry(deptry, report)
        if deptry_crashed(result, report):
            if deptry_found_no_declaration(result):
                declarations = unreadable_declarations()
                if declarations:
                    print(json.dumps(unchecked_dependencies(declarations)))
                    return 0
                print(json.dumps([]))
                return 0
            sys.stderr.write(result.stderr)
            return 2
        print(json.dumps(findings(unused_dependencies(report))))
    return 0


if __name__ == "__main__":
    sys.exit(main())

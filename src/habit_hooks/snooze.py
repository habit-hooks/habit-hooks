"""habit-snooze: drop issues whose ``key`` is in a checked-in index.

As a transformer it reads findings on stdin and passes through everything it
does not drop. ``--snooze`` / ``--prune`` / ``--list`` maintain the index; the
transform itself only reads it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

INDEX_PATH = Path(".habit-hooks") / "snooze.json"


def load_index(project_dir: Path) -> list[str]:
    path = project_dir / INDEX_PATH
    if not path.exists():
        return []
    return json.loads(path.read_text())


def save_index(keys: list[str], project_dir: Path) -> None:
    path = project_dir / INDEX_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sorted(set(keys))) + "\n")


def finding_keys(findings: list[dict]) -> list[str]:
    return [issue["key"] for finding in findings for issue in finding["issues"]]


def transform(findings: list[dict], snoozed: set[str]) -> list[dict]:
    """Drop snoozed issues, and any finding whose last issue we just dropped.

    A finding that arrives with no issues is passed through rather than dropped:
    nothing in it was snoozed. That keeps an empty index a true no-op, which
    matters now that snooze runs by default.
    """
    kept = []
    for finding in findings:
        issues = [issue for issue in finding["issues"] if issue["key"] not in snoozed]
        snoozed_them_all = finding["issues"] and not issues
        if not snoozed_them_all:
            kept.append({**finding, "issues": issues})
    return kept


def read_findings() -> list[dict]:
    raw = sys.stdin.read().strip()
    return json.loads(raw) if raw else []


def run(args: argparse.Namespace, project_dir: Path) -> int:
    if args.list:
        for key in load_index(project_dir):
            sys.stdout.write(key + "\n")
        return 0
    if args.snooze:
        save_index(load_index(project_dir) + finding_keys(read_findings()), project_dir)
        return 0
    if args.prune:
        present = set(finding_keys(read_findings()))
        save_index([k for k in load_index(project_dir) if k in present], project_dir)
        return 0
    kept = transform(read_findings(), set(load_index(project_dir)))
    sys.stdout.write(json.dumps(kept) + "\n")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="habit-snooze")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--snooze", action="store_true")
    group.add_argument("--prune", action="store_true")
    group.add_argument("--list", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    return run(args, Path.cwd())


if __name__ == "__main__":
    sys.exit(main())

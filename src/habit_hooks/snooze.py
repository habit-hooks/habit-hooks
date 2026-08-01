"""habit-snooze: drop issues whose ``key`` is in a checked-in index.

As a transformer it reads findings on stdin and passes through everything it
does not drop. ``--snooze`` / ``--prune`` / ``--list`` maintain the index; the
transform itself only reads it.

``--until-changed`` makes the index a ratchet instead of a permanent exemption
list: a snooze then holds only while the file it was recorded against is
unchanged since this branch left the project's base ref. It ships as its own
transformer (``snooze-until-changed``) so a project opts into that, and the
default ``snooze`` keeps dropping unconditionally, asking git nothing.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Collection
from pathlib import Path

from .changed_files import changed_against_base
from .config import load_config

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


def anchor_file(issue: dict) -> str:
    """The file an issue's snooze is anchored to: its ``details.file``, else its key.

    A sensor keys an issue by whatever groups it best — a module or export name,
    not always a path — so the file to compare comes from the details bag.
    """
    return issue.get("details", {}).get("file", issue["key"])


def transform(
    findings: list[dict], snoozed: set[str], lapsed: Collection[str] = frozenset()
) -> list[dict]:
    """Drop snoozed issues, and any finding whose last issue we just dropped.

    ``snoozed`` holds keys, ``lapsed`` the files whose snooze no longer applies:
    an issue anchored to one of those changed, so its debt is due again.

    A finding that arrives with no issues is passed through rather than dropped:
    nothing in it was snoozed. That keeps an empty index a true no-op, which
    matters now that snooze runs by default.
    """
    kept = []
    for finding in findings:
        issues = [
            issue
            for issue in finding["issues"]
            if not _still_snoozed(issue, snoozed, lapsed)
        ]
        snoozed_them_all = finding["issues"] and not issues
        if not snoozed_them_all:
            kept.append({**finding, "issues": issues})
    return kept


def _still_snoozed(issue: dict, snoozed: set[str], lapsed: Collection[str]) -> bool:
    return issue["key"] in snoozed and anchor_file(issue) not in lapsed


def lapsed_files(findings: list[dict], snoozed: set[str], project_dir: Path) -> set[str]:
    """The snoozed issues' files that changed against the project's base ref."""
    anchors = {
        anchor_file(issue)
        for finding in findings
        for issue in finding["issues"]
        if issue["key"] in snoozed
    }
    base_ref = load_config(project_dir).scope.branchBase
    return changed_against_base(anchors, project_dir, base_ref)


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
    return _write_transformed(project_dir, args.until_changed)


def _write_transformed(project_dir: Path, until_changed: bool) -> int:
    findings = read_findings()
    snoozed = set(load_index(project_dir))
    lapsed = lapsed_files(findings, snoozed, project_dir) if until_changed else set()
    sys.stdout.write(json.dumps(transform(findings, snoozed, lapsed)) + "\n")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="habit-snooze")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--snooze", action="store_true")
    group.add_argument("--prune", action="store_true")
    group.add_argument("--list", action="store_true")
    parser.add_argument("--until-changed", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    return run(args, Path.cwd())


if __name__ == "__main__":
    sys.exit(main())

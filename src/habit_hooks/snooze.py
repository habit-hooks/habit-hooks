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
from .cli import EXIT_TOOL_ERROR, add_version_flag, run_console
from .config import load_config
from .snooze_index import INDEX_PATH, SnoozeError, load_index, save_index

__all__ = ["INDEX_PATH", "SnoozeError", "load_index", "main", "save_index"]

# The transformers that filter findings through this index. `habit-sensors
# --no-snooze` strips them so `--prune` can compare the index against a
# snooze-free view of the run instead of one snooze already emptied (#94).
SNOOZE_TRANSFORMERS = frozenset({"snooze", "snooze-until-changed"})


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


def snoozed_anchors(findings: list[dict], snoozed: set[str]) -> set[str]:
    """The files the snoozed issues sit in — where a lapse could apply."""
    return {
        anchor_file(issue)
        for finding in findings
        for issue in finding["issues"]
        if issue["key"] in snoozed
    }


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
        return _prune(project_dir)
    return _write_transformed(project_dir, args.until_changed, args.config)


def _prune(project_dir: Path) -> int:
    """Drop index keys the latest run no longer reports — but never on an empty
    run. Empty findings mean "nothing was measured" (an empty scope, or a
    snooze-filtered pipe), not "every exemption is obsolete"; emptying the whole
    index on that is the false-clean class of #78/#84, so it is refused (#94).
    The run must be fed snooze-free (`habit-sensors --no-snooze`), else every
    still-violating key is missing from stdin and would be pruned away.
    """
    present = set(finding_keys(read_findings()))
    index = load_index(project_dir)
    if index and not present:
        sys.stderr.write(
            "habit-snooze: --prune read no findings; refusing to empty a "
            "populated index. Nothing was measured — feed it a snooze-free run "
            "(`habit-sensors --no-snooze | habit-snooze --prune`). "
            "Index left unchanged.\n"
        )
        return 1
    save_index([key for key in index if key in present], project_dir)
    return 0


def _write_transformed(
    project_dir: Path, until_changed: bool, config_path: Path | None
) -> int:
    """Drop snoozed findings, lapsing any whose anchor file changed since the base.

    The base ref comes from the run's ``--config`` — the same file the sensors
    stage scoped from — so the whole run answers with one ``[scope] branchBase``,
    not a silent fall back to ``.habit-hooks/config.toml`` (#86).
    """
    findings = read_findings()
    snoozed = set(load_index(project_dir))
    lapsed: set[str] = set()
    if until_changed:
        base_ref = load_config(project_dir, config_path).scope.branchBase
        anchors = snoozed_anchors(findings, snoozed)
        lapsed = changed_against_base(anchors, project_dir, base_ref)
    sys.stdout.write(json.dumps(transform(findings, snoozed, lapsed)) + "\n")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="habit-snooze")
    add_version_flag(parser)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--snooze", action="store_true")
    group.add_argument("--prune", action="store_true")
    group.add_argument("--list", action="store_true")
    parser.add_argument("--until-changed", action="store_true")
    parser.add_argument("--config", type=Path)
    args = parser.parse_args(argv)
    _reject_until_changed_with_index_op(parser, args)
    return args


def _reject_until_changed_with_index_op(
    parser: argparse.ArgumentParser, args: argparse.Namespace
) -> None:
    """``--until-changed`` ratchets the transform and has no bearing on the index
    operations. Combining them used to be accepted and silently dropped (#86);
    name the conflict instead of ignoring one of the two flags."""
    if not args.until_changed:
        return
    for index_op in ("snooze", "prune", "list"):
        if getattr(args, index_op):
            parser.error(f"argument --until-changed: not allowed with --{index_op}")


def main(argv: list[str] | None = None) -> int:
    return run_console(parse_args, _run_snooze_command, argv)


def _run_snooze_command(args: argparse.Namespace) -> int:
    """A corrupt index is a failure of the tool itself — a checked-in file a human
    edits, not a statement about the code — so it exits 2 like a rejected config
    or an unresolvable ref (#103). The `--prune` refusal is the other kind, a
    judgement about the run, and keeps exit 1.
    """
    try:
        return run(args, Path.cwd())
    except SnoozeError as error:
        sys.stderr.write(f"habit-snooze: {error}\n")
        return EXIT_TOOL_ERROR


if __name__ == "__main__":
    sys.exit(main())

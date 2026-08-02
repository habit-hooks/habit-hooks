"""Pick the files the leaf sensors see, then expose them as ``scope.files``.

The scope flags are mutually exclusive; with none, the scope is derived from the
``[scope]`` config. Git-backed modes ask ``git_history`` — the same question, in
the same words, that a lapsing snooze asks. Whatever mode picked them, the paths
are placed in the project and then narrowed to the files the work tree still has
and ``[files]`` still calls source. File selection uses pathspec (gitignore)
globbing — no brace expansion.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path

import pathspec

from . import git_history
from .config import Config
from .project_paths import project_relative

# What to tell someone whose base ref is not in their checkout, named after
# whatever chose the ref — the setting they can act on differs per mode.
_BRANCH_BASE_SETTING = "set [scope] branchBase to a ref it has"
_BRANCH_FLAG = "pass --branch a ref it has"
_SINCE_FLAG = "pass --since a ref it has"


@dataclass
class Scope:
    files: list[str]
    # Why a run scanned nothing, when that is worth saying out loud. Non-fatal:
    # the hook behind `--file` fires on every edited file, including the ones a
    # project rightly does not scan.
    notices: list[str] = field(default_factory=list)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="habit-sensors")
    parser.add_argument("--config", type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--all", action="store_true")
    modes.add_argument("--file")
    modes.add_argument("--branch", nargs="?", const="", metavar="base")
    modes.add_argument("--last", type=int)
    modes.add_argument("--since")
    return parser.parse_args(argv)


def resolve_scope(
    args: argparse.Namespace, config: Config, project_dir: Path
) -> Scope:
    """The files this run measures: the chosen mode's paths, narrowed to source."""
    picked = _selected(args, config, project_dir)
    files = _source_files(picked, config, project_dir)
    return Scope(files, _named_file_notices(args.file, project_dir, files))


def _selected(
    args: argparse.Namespace, config: Config, project_dir: Path
) -> list[str]:
    """The paths the chosen mode picks out, before any narrowing."""
    if args.file is not None:
        return [args.file]
    if args.branch is not None:
        base = args.branch or config.scope.branchBase
        return _changed_since(
            project_dir, base, _BRANCH_FLAG if args.branch else _BRANCH_BASE_SETTING
        )
    if args.last is not None:
        return _changed_in_last_commits(project_dir, args.last)
    if args.since is not None:
        return _changed_since(project_dir, args.since, _SINCE_FLAG)
    if args.all:
        return _every_file(project_dir)
    return _configured_scope(config, project_dir)


def _configured_scope(config: Config, project_dir: Path) -> list[str]:
    if not git_history.places_directory(project_dir):
        return _every_file(project_dir)
    if config.scope.changedOnly:
        return git_history.changed_paths(project_dir, [])
    on_main = git_history.head_branch(project_dir) == config.scope.mainBranch
    if config.scope.autoBranchOffMain and not on_main:
        return _changed_since(
            project_dir, config.scope.branchBase, _BRANCH_BASE_SETTING
        )
    return _every_file(project_dir)


def _source_files(paths: list[str], config: Config, project_dir: Path) -> list[str]:
    """The paths a sensor can be asked about: files that are there, and are source.

    All three narrowings belong here rather than in each sensor. A path is first
    placed in the project, because a hook hands ``--file`` an absolute path and
    no relative glob matches one. Git names every path a branch deleted, and a
    file that is gone has no smells left to find. And ``[files]`` is what a
    project already uses to say what its source is, so a lockfile bump is out of
    a git-derived scope exactly as it is out of ``--all``.

    No ``[files]`` at all is a project with no opinion, so everything is source;
    an empty ``[files]`` is a project saying its source is nothing.
    """
    placed = (project_relative(path, project_dir) for path in paths)
    present = [path for path in placed if path and (project_dir / path).is_file()]
    if config.files is None:
        return present
    spec = pathspec.PathSpec.from_lines("gitignore", config.files)
    return [path for path in present if spec.match_file(path)]


def _named_file_notices(
    named: str | None, project_dir: Path, scoped: list[str]
) -> list[str]:
    """Why ``--file`` scanned nothing, since a run that scans nothing reports clean.

    The same reasoning that makes an unresolvable base ref fail the run: silence
    about a run that measured nothing is indistinguishable from a clean one.
    """
    if named is None or scoped:
        return []
    placed = project_relative(named, project_dir)
    missing = placed is None or not (project_dir / placed).is_file()
    reason = "is not a file in this project" if missing else "is outside [files]"
    return [f"habit-sensors: --file {named!r} {reason}; nothing scanned"]


def _every_file(project_dir: Path) -> list[str]:
    return sorted(
        str(path.relative_to(project_dir))
        for path in project_dir.rglob("*")
        if path.is_file()
    )


def _changed_since(project_dir: Path, ref: str, remedy: str) -> list[str]:
    """What this branch changed since it left ``ref``."""
    _require_git_repo(project_dir)
    fork_point = _fork_point(project_dir, ref, remedy)
    return git_history.changed_paths(project_dir, [fork_point])


def _fork_point(project_dir: Path, ref: str, remedy: str) -> str:
    """Where this branch left ``ref``, or a failed run naming it and the remedy.

    Git answers a ref it does not have with an empty diff and a message nobody
    reads, so the run would scan nothing and report every sensor clean — the
    silent green of a typo'd ``branchBase``, or of a CI checkout that never
    fetched the base.
    """
    tip = git_history.resolves(project_dir, ref)
    if tip is None:
        raise SystemExit(
            f"habit-sensors: base ref {ref!r} does not resolve in this checkout "
            f"— {remedy}"
        )
    return git_history.forked_at(project_dir, ref, tip)


def _changed_in_last_commits(project_dir: Path, count: int) -> list[str]:
    """What the last ``count`` commits changed, uncommitted work aside.

    A count is not a ref, so a history shorter than the question is not the
    mistake a mistyped ref is: a young repository, or a shallow CI clone, means
    "everything so far". The base clamps to the state before the first commit
    rather than failing — and scanning more than asked is never a silent green.
    """
    _require_git_repo(project_dir)
    depth = git_history.resolves(project_dir, f"HEAD~{count}")
    since = depth or git_history.empty_tree(project_dir)
    return git_history.changed_paths(project_dir, [since, "HEAD"])


def _require_git_repo(project_dir: Path) -> None:
    if not git_history.places_directory(project_dir):
        raise SystemExit("habit-sensors: not a git repository")

"""Pick the files the leaf sensors see, then expose them as ``scope.files``.

The scope flags are mutually exclusive; with none, the scope is derived from the
``[scope]`` config. Git-backed modes measure a branch from the same merge base a
lapsing snooze asks ``git_history`` for, then widen the answer to the uncommitted
work in progress — the staged and untracked files a diff alone would miss (#92).
Whole-project modes ask ``project_scan`` for the files the project keeps, which
is git's answer too, so no mode measures a universe another one cannot see
(#142). The picked paths are then narrowed to the files the work tree still has
and ``[files]`` calls source (pathspec/gitignore globbing, no brace expansion).
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path

from . import git_history, project_scan
from .path_globs import matching
from .cli import ToolError
from .config import Config
from .project_paths import project_relative
from .scope_notices import empty_scope_notices, submodule_notices

# What to tell someone whose base ref is not in their checkout, named after
# whatever chose the ref — the setting they can act on differs per mode.
_BRANCH_BASE_SETTING = "set [scope] branchBase to a ref it has"
_BRANCH_FLAG = "pass --branch a ref it has"
_SINCE_FLAG = "pass --since a ref it has"


@dataclass
class Scope:
    files: list[str]
    # What the reader must know about this scope that its files do not show: why
    # it came out empty, and any submodule it left out. Non-fatal, and written to
    # stderr — a `--file` hook fires on every edit, including files a project
    # won't scan, and a gap in a scan is not itself a finding.
    notices: list[str] = field(default_factory=list)


def resolve_scope(args: argparse.Namespace, config: Config, project_dir: Path) -> Scope:
    """The files this run measures: the chosen mode's paths, narrowed to source.

    Discovery is opt-in (#97): with no ``[files]`` at all, every mode narrows to
    nothing and the run says why. A git mode still resolves its base ref first,
    so a typo'd ref fails loudly rather than being masked by an empty opt-in.

    Two things are worth saying about a scope, and only one of them is about an
    empty one: a submodule left out shrinks a scan that still has plenty to
    measure, and unsaid it would render ✅ over the gap.
    """
    placed = _placed(_selected(args, config, project_dir), project_dir)
    files = _source_files(placed, config, project_dir)
    notices = [] if files else empty_scope_notices(args.file, project_dir, config)
    if args.file is None:
        # Policy, not correctness: `submodule_paths` would identify a submodule
        # given to `--file` perfectly well. But that mode answers about the one
        # path the caller named, `_named_file_notice` already says a directory
        # is not a file, and a second line about it would only repeat that.
        notices = [*submodule_notices(placed, config, project_dir), *notices]
    return Scope(files, notices)


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
        return _every_file(config, project_dir)
    return _configured_scope(config, project_dir)


def _configured_scope(config: Config, project_dir: Path) -> list[str]:
    if not git_history.places_directory(project_dir):
        return _every_file(config, project_dir)
    if config.scope.changedOnly:
        return _with_work_in_progress(project_dir, [])
    on_main = git_history.head_branch(project_dir) == config.scope.mainBranch
    if config.scope.autoBranchOffMain and not on_main:
        return _changed_since(
            project_dir, config.scope.branchBase, _BRANCH_BASE_SETTING
        )
    return _every_file(config, project_dir)


def _placed(paths: list[str], project_dir: Path) -> list[str]:
    """Each path under the project's own name for it, dropping any outside it.

    Split from the narrowing below because the notices need these too: a
    submodule is recognised by being a directory, so it has to be recognised
    before the step that keeps only files throws it away.
    """
    named = (project_relative(path, project_dir) for path in paths)
    return [path for path in named if path]


def _source_files(placed: list[str], config: Config, project_dir: Path) -> list[str]:
    """The paths a sensor can be asked about: files that are there, and are source.

    Both narrowings belong here, not in each sensor: a path a branch deleted is
    dropped (a gone file has no smells left, and a submodule's own directory is
    not a file either); and ``[files]`` keeps only source, so a lockfile bump is
    out of a git-derived scope as it is out of ``--all``. No ``[files]`` and an
    empty one keep nothing (#97).
    """
    present = [path for path in placed if (project_dir / path).is_file()]
    return matching(present, config.files or [])


def _every_file(config: Config, project_dir: Path) -> list[str]:
    """Every file the project has, once there is a ``[files]`` to narrow it to.

    Discovery is opt-in (#97): with none, nothing is enumerated and git is never
    asked — a default install must not walk ``node_modules`` only to discard it.
    What counts as the project's own files, and why git rather than the disk
    answers that, is ``project_scan``.
    """
    if config.files is None:
        return []
    return project_scan.files_in(project_dir)


def _with_work_in_progress(project_dir: Path, tracked: list[str]) -> list[str]:
    """``tracked`` history widened with the uncommitted work in progress: a diff
    misses the untracked file just written and, commit-to-commit, staged edits
    too (#92). ``_source_files`` still narrows the union to present source after.
    """
    combined = [*tracked, *git_history.uncommitted_changes(project_dir)]
    return list(dict.fromkeys(combined))


def _changed_since(project_dir: Path, ref: str, remedy: str) -> list[str]:
    """What this branch changed since it left ``ref``, plus its work in progress."""
    _require_git_repo(project_dir)
    fork_point = _fork_point(project_dir, ref, remedy)
    return _with_work_in_progress(
        project_dir, git_history.changed_paths(project_dir, [fork_point])
    )


def _fork_point(project_dir: Path, ref: str, remedy: str) -> str:
    """Where this branch left ``ref``, or a failed run naming it and the remedy.

    Git answers a ref it does not have with an empty diff and a message nobody
    reads, so the run would scan nothing and report every sensor clean — the
    silent green of a typo'd ``branchBase``, or of a CI checkout that never
    fetched the base.
    """
    tip = git_history.resolves(project_dir, ref)
    if tip is None:
        raise ToolError(
            f"habit-sensors: base ref {ref!r} does not resolve in this checkout "
            f"— {remedy}"
        )
    return git_history.forked_at(project_dir, ref, tip)


def _changed_in_last_commits(project_dir: Path, count: int) -> list[str]:
    """What the last ``count`` commits changed, plus the current work in progress.

    A count is not a ref: a history shorter than the question means "everything
    so far", not the mistake a mistyped ref is. The base clamps to before the
    first commit rather than failing, and over-scanning never reads as clean.
    """
    _require_git_repo(project_dir)
    depth = git_history.resolves(project_dir, f"HEAD~{count}")
    since = depth or git_history.empty_tree(project_dir)
    return _with_work_in_progress(
        project_dir, git_history.changed_paths(project_dir, [since, "HEAD"])
    )


def _require_git_repo(project_dir: Path) -> None:
    if not git_history.places_directory(project_dir):
        raise ToolError("habit-sensors: not a git repository")

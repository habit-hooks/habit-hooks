"""Pick the files the leaf sensors see, then expose them as ``scope.files``.

The scope flags are mutually exclusive; with none, the scope is derived from the
``[scope]`` config. Git-backed modes measure a branch from the same merge base a
lapsing snooze asks ``git_history`` for, then widen the answer to the uncommitted
work in progress — the staged and untracked files a diff alone would miss (#92).
The picked paths are then narrowed to the files the work tree still has and
``[files]`` calls source (pathspec/gitignore globbing, no brace expansion).
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path

import pathspec

from . import git_history
from .cli import ToolError
from .config import Config
from .project_paths import project_relative

# What to tell someone whose base ref is not in their checkout, named after
# whatever chose the ref — the setting they can act on differs per mode.
_BRANCH_BASE_SETTING = "set [scope] branchBase to a ref it has"
_BRANCH_FLAG = "pass --branch a ref it has"
_SINCE_FLAG = "pass --since a ref it has"

# Discovery is opt-in (#97): a project that names no source scans nothing. Said
# out loud, since silence about a run that measured nothing reads as clean.
_NO_FILES_NOTICE = (
    "habit-sensors: no [files] are configured — name what to scan in "
    ".habit-hooks/config.toml; nothing scanned"
)


@dataclass
class Scope:
    files: list[str]
    # Why a run scanned nothing, when that is worth saying out loud. Non-fatal:
    # a `--file` hook fires on every edit, including files a project won't scan.
    notices: list[str] = field(default_factory=list)


def resolve_scope(args: argparse.Namespace, config: Config, project_dir: Path) -> Scope:
    """The files this run measures: the chosen mode's paths, narrowed to source.

    Discovery is opt-in (#97): with no ``[files]`` at all, every mode narrows to
    nothing and the run says why. A git mode still resolves its base ref first,
    so a typo'd ref fails loudly rather than being masked by an empty opt-in.
    """
    picked = _selected(args, config, project_dir)
    files = _source_files(picked, config, project_dir)
    if args.file is not None:
        return Scope(files, _named_file_notices(args.file, project_dir, files))
    return Scope(files, [_NO_FILES_NOTICE] if config.files is None else [])


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


def _source_files(paths: list[str], config: Config, project_dir: Path) -> list[str]:
    """The paths a sensor can be asked about: files that are there, and are source.

    All three narrowings belong here, not in each sensor: a path is placed in the
    project (a hook hands ``--file`` an absolute path no relative glob matches);
    one a branch deleted is dropped (a gone file has no smells left); and
    ``[files]`` keeps only source, so a lockfile bump is out of a git-derived
    scope as it is out of ``--all``. No ``[files]`` and an empty one keep nothing
    (#97).
    """
    placed = (project_relative(path, project_dir) for path in paths)
    present = [path for path in placed if path and (project_dir / path).is_file()]
    return matching(present, config.files or [])


def matching(paths: list[str], globs: list[str]) -> list[str]:
    """The ``paths`` kept by pathspec (gitignore) ``globs``, order preserved.

    The one place a path list is filtered by a glob list: the run's ``[files]``
    and a single sensor's own ``files`` narrowing in ``execution.py``.
    """
    spec = pathspec.PathSpec.from_lines("gitignore", globs)
    return [path for path in paths if spec.match_file(path)]


def _named_file_notices(
    named: str | None, project_dir: Path, scoped: list[str]
) -> list[str]:
    """Why ``--file`` scanned nothing: silence about a run that measured nothing
    is indistinguishable from a clean one, as with an unresolvable base ref.
    """
    if named is None or scoped:
        return []
    placed = project_relative(named, project_dir)
    missing = placed is None or not (project_dir / placed).is_file()
    reason = "is not a file in this project" if missing else "is outside [files]"
    return [f"habit-sensors: --file {named!r} {reason}; nothing scanned"]


def _every_file(config: Config, project_dir: Path) -> list[str]:
    """Every file under the project, once there is a ``[files]`` to narrow it to.

    Discovery is opt-in (#97): with none, nothing is enumerated — a default
    install never walks ``node_modules`` or ``.venv`` only to discard the lot.
    """
    if config.files is None:
        return []
    return sorted(
        str(path.relative_to(project_dir))
        for path in project_dir.rglob("*")
        if path.is_file()
    )


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

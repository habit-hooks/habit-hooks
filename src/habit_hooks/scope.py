
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

_BRANCH_BASE_SETTING = "set [scope] branchBase to a ref it has"
_BRANCH_FLAG = "pass --branch a ref it has"
_SINCE_FLAG = "pass --since a ref it has"


@dataclass
class Scope:
    files: list[str]
    notices: list[str] = field(default_factory=list)


def resolve_scope(args: argparse.Namespace, config: Config, project_dir: Path) -> Scope:
    placed = _placed(_selected(args, config, project_dir), project_dir)
    files = _source_files(placed, config, project_dir)
    notices = [] if files else empty_scope_notices(args.file[-1] if args.file else None, project_dir, config)
    if args.file is None:
        notices = [*submodule_notices(placed, config, project_dir), *notices]
    return Scope(files, notices)


def _selected(
    args: argparse.Namespace, config: Config, project_dir: Path
) -> list[str]:
    if args.file is not None:
        return args.file
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
    named = (project_relative(path, project_dir) for path in paths)
    return [path for path in named if path]


def _source_files(placed: list[str], config: Config, project_dir: Path) -> list[str]:
    present = [path for path in placed if (project_dir / path).is_file()]
    return matching(present, config.files or [])


def _every_file(config: Config, project_dir: Path) -> list[str]:
    if config.files is None:
        return []
    return project_scan.files_in(project_dir)


def _with_work_in_progress(project_dir: Path, tracked: list[str]) -> list[str]:
    combined = [*tracked, *git_history.uncommitted_changes(project_dir)]
    return list(dict.fromkeys(combined))


def _changed_since(project_dir: Path, ref: str, remedy: str) -> list[str]:
    _require_git_repo(project_dir)
    fork_point = _fork_point(project_dir, ref, remedy)
    return _with_work_in_progress(
        project_dir, git_history.changed_paths(project_dir, [fork_point])
    )


def _fork_point(project_dir: Path, ref: str, remedy: str) -> str:
    tip = git_history.resolves(project_dir, ref)
    if tip is None:
        raise ToolError(
            f"habit-sensors: base ref {ref!r} does not resolve in this checkout "
            f"— {remedy}"
        )
    return git_history.forked_at(project_dir, ref, tip)


def _changed_in_last_commits(project_dir: Path, count: int) -> list[str]:
    _require_git_repo(project_dir)
    depth = git_history.resolves(project_dir, f"HEAD~{count}")
    since = depth or git_history.empty_tree(project_dir)
    return _with_work_in_progress(
        project_dir, git_history.changed_paths(project_dir, [since, "HEAD"])
    )


def _require_git_repo(project_dir: Path) -> None:
    if not git_history.places_directory(project_dir):
        raise ToolError("habit-sensors: not a git repository")

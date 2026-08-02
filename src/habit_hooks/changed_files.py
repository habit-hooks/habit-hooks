"""Ask git which files this branch changed since it left the base ref.

This is what lets a snooze lapse: an exemption recorded against a file is only
honoured while that file is untouched. The question itself belongs to
``git_history`` and is shared with the scoped run; what is decided here is what
to make of git's two silences. A path git cannot place reads as "unchanged" so
the snooze holds, while a base ref a real repository cannot resolve fails the
run, because answering "unchanged" for every file would quietly make every
snooze permanent again.
"""

from __future__ import annotations

from collections.abc import Collection
from pathlib import Path

from . import git_history
from .cli import ToolError
from .project_paths import project_relative


def changed_against_base(
    files: Collection[str], project_dir: Path, base_ref: str
) -> set[str]:
    """The subset of ``files`` that differs from where this branch left ``base_ref``.

    "Differs" covers both legs a reviewer would call a change: work committed on
    the branch, and edits still sitting in the working tree. With nothing to
    compare, git is not asked anything at all.
    """
    if not files:
        return set()
    comparison_point = _comparison_point(project_dir, base_ref)
    if comparison_point is None:
        return set()
    placed = {file: project_relative(file, project_dir) for file in files}
    changed = _changed_paths(project_dir, comparison_point, placed.values())
    return {file for file, path in placed.items() if path in changed}


def _comparison_point(project_dir: Path, base_ref: str) -> str | None:
    """The commit to compare against: where this branch left ``base_ref``.

    ``None`` means git could not place this directory at all — no repository, or
    no git — and every snooze holds.
    """
    if not git_history.places_directory(project_dir):
        return None
    tip = git_history.resolves(project_dir, base_ref)
    if tip is None:  # a real repository, without the configured ref
        raise ToolError(
            f"habit-snooze: base ref {base_ref!r} does not resolve in this checkout — "
            "set [scope] branchBase to a ref it has"
        )
    return git_history.forked_at(project_dir, base_ref, tip)


def _changed_paths(
    project_dir: Path, comparison_point: str, paths: Collection[str | None]
) -> set[str]:
    """The paths git names when diffing that commit against the work tree.

    One question for the whole set, rather than one per file at ~39ms of process
    spawn each — in a tool that runs on every hook, over a set as large as a
    legacy repo's freshly-snoozed baseline.

    A path the project cannot place is left out of the question entirely. One
    path outside the repository makes git fail the whole call, which would read
    as "nothing changed" for every other path in it; and ``--relative`` could not
    name such a path back to us anyway. Those paths therefore read as unchanged,
    the same safe degrade an untracked file gets. When *every* path drops out,
    git is asked nothing at all — an empty pathspec list would otherwise ask
    about the whole tree.
    """
    pathspecs = [path for path in paths if path is not None]
    if not pathspecs:
        return set()
    return set(git_history.changed_paths(project_dir, [comparison_point], pathspecs))

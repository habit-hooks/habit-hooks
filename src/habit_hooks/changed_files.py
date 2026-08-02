"""Ask git which files this branch changed since it left the base ref.

This is what lets a snooze lapse: an exemption recorded against a file is only
honoured while that file is untouched. Two kinds of git silence are kept apart —
a path git cannot place reads as "unchanged" so the snooze holds, while a base
ref a real repository cannot resolve fails the run, because answering
"unchanged" for every file would quietly make every snooze permanent again.
"""

from __future__ import annotations

import subprocess
from collections.abc import Collection, Iterator
from pathlib import Path

from .project_paths import project_relative

# git's fatal exit: no repository here, or one it cannot read. `git rev-parse
# --verify --quiet` uses it for exactly that, and 1 for "the repository is fine,
# the ref is not" — which is what separates the two silences.
_GIT_FATAL = 128

# Bytes of pathspec per `git diff`. Well under the smallest ARG_MAX we run on
# (macOS, 1MB) with room to spare for the environment a spawn carries with it.
_ARGUMENT_BUDGET = 100_000


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
    """The commit to compare against: the merge base of ``base_ref`` and ``HEAD``.

    Starting there rather than at the base ref's tip keeps a branch measured
    against the debt it touched itself, so work landed on the base ref afterwards
    lapses nothing. ``None`` means git could not place this directory at all — no
    repository, or no git — and every snooze holds.
    """
    verified = _git(
        project_dir, "rev-parse", "--verify", "--quiet", f"{base_ref}^{{commit}}"
    )
    if verified is None or verified.returncode == _GIT_FATAL:
        return None  # no git, or no repository to ask about
    if verified.returncode != 0:  # a real repository, without the configured ref
        raise SystemExit(
            f"habit-snooze: base ref {base_ref!r} does not resolve in this checkout — "
            "set [scope] branchBase to a ref it has"
        )
    forked_at = _git_stdout(project_dir, "merge-base", base_ref, "HEAD")
    return forked_at or verified.stdout.strip()  # no common ancestor: the ref itself


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
    the same safe degrade an untracked file gets.
    """
    pathspecs = sorted(path for path in paths if path is not None)
    changed: set[str] = set()
    for batch in _within_argument_limits(pathspecs):
        changed |= _diff_names(project_dir, comparison_point, batch)
    return changed


def _within_argument_limits(pathspecs: list[str]) -> Iterator[list[str]]:
    """``pathspecs`` split into command lines the operating system will accept.

    Snoozing a legacy repo wholesale — the documented way in — can name tens of
    thousands of files, and an argument list past ARG_MAX makes the spawn fail
    outright. That reads as "nothing changed", which is the one answer that makes
    every snooze permanent: the very failure batching was meant to avoid.
    """
    batch: list[str] = []
    length = 0
    for path in pathspecs:
        if batch and length + len(path) > _ARGUMENT_BUDGET:
            yield batch
            batch, length = [], 0
        batch.append(path)
        length += len(path) + 1
    if batch:
        yield batch


def _diff_names(
    project_dir: Path, comparison_point: str, pathspecs: list[str]
) -> set[str]:
    """One ``git diff`` over one batch of paths, answered by name.

    ``--literal-pathspecs`` keeps every path a plain path: a key like
    ``:!src/a.py`` is otherwise read as *exclude* ``src/a.py`` and silently drops
    it from the answer, and one with unknown magic (``:(bad)x``) makes git fail
    the whole batch. ``--relative`` asks and answers in the project's own terms,
    so a project below the repository root compares like with like. ``-z`` stops
    git from quoting a non-ASCII name (``"caf\\303\\251.py"``), which would then
    match nothing.
    """
    named = _git_stdout(
        project_dir,
        "--literal-pathspecs",
        "diff",
        "--name-only",
        "-z",
        "--relative",
        comparison_point,
        "--",
        *pathspecs,
    )
    return {path for path in named.split("\0") if path}


def _git(project_dir: Path, *args: str) -> subprocess.CompletedProcess[str] | None:
    """``git <args>`` in the project, or ``None`` when git could not be run at all."""
    try:
        return subprocess.run(
            ["git", *args], cwd=project_dir, capture_output=True, text=True
        )
    except OSError:
        return None


def _git_stdout(project_dir: Path, *args: str) -> str:
    """``git <args>`` output, or empty on any failure — the safe degrade."""
    result = _git(project_dir, *args)
    if result is None or result.returncode != 0:
        return ""
    return result.stdout.strip()

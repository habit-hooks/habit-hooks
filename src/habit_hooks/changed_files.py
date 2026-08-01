"""Ask git which files this branch changed since it left the base ref.

This is what lets a snooze lapse: an exemption recorded against a file is only
honoured while that file is untouched. Two kinds of git silence are kept apart —
a path git cannot place reads as "unchanged" so the snooze holds, while a base
ref a real repository cannot resolve fails the run, because answering
"unchanged" for every file would quietly make every snooze permanent again.
"""

from __future__ import annotations

import subprocess
from collections.abc import Collection
from pathlib import Path

# git's fatal exit: no repository here, or one it cannot read. `git rev-parse
# --verify --quiet` uses it for exactly that, and 1 for "the repository is fine,
# the ref is not" — which is what separates the two silences.
_GIT_FATAL = 128


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
    return {file for file in files if _differs(file, project_dir, comparison_point)}


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


def _differs(file: str, project_dir: Path, comparison_point: str) -> bool:
    """Whether git names ``file`` when diffing that commit against the work tree.

    ``--literal-pathspecs`` stops a path that reads as a glob (``app/[slug]/…``)
    from matching its neighbours, and ``-- <file>`` keeps the question about that
    one file: anything git cannot place names nothing back.
    """
    return bool(
        _git_stdout(
            project_dir,
            "--literal-pathspecs",
            "diff",
            "--name-only",
            comparison_point,
            "--",
            file,
        )
    )


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

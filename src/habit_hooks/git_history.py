"""Ask git where a branch left its base ref, and which paths differ since.

Two callers put the same question in the same words — a scoped run
(``scope.py``) and a lapsing snooze (``changed_files.py``) — and they differ only
in what they make of silence. The facts live here so there is one answer:
``[scope] branchBase`` cannot come to mean one thing in a run and another in a
snooze, and a flag this module gets right cannot be missing from the other
caller. Each caller keeps its own policy for the two silences: a directory git
cannot place, and a ref a real repository does not have.
"""

from __future__ import annotations

import subprocess
from collections.abc import Collection
from pathlib import Path

from .argv_budget import within_argument_limits


def places_directory(project_dir: Path) -> bool:
    """Whether git can place this directory in a repository at all.

    False covers both ways git can say nothing: no repository here, and no git
    to ask. Neither is a mistake a message could help with, so each caller
    degrades rather than failing on it.
    """
    placed = _run(project_dir, "rev-parse", "--is-inside-work-tree")
    return placed is not None and placed.returncode == 0


def resolves(project_dir: Path, ref: str) -> str | None:
    """The commit ``ref`` names here, or ``None`` when this checkout has no such ref.

    Git answers a ref it never heard of with an empty diff, which reads as "this
    branch changed nothing" — a clean run over an unscanned tree.
    ``--verify --quiet`` is what tells the two apart.
    """
    verified = _run(project_dir, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    if verified is None or verified.returncode != 0:
        return None
    return verified.stdout.strip()


def forked_at(project_dir: Path, ref: str, tip: str) -> str:
    """Where this branch left ``ref``: its merge base with ``HEAD``, else ``tip``.

    Starting at the merge base rather than the ref's tip keeps a branch measured
    against what it touched itself, so work landed on the base afterwards is
    neither scanned nor lapsed. Histories with no common ancestor — an orphan
    branch, two repositories grafted together — leave git with no merge base to
    name, and the ref's own tip is then the only comparison there is; comparing
    against nothing would scope a run to nothing.
    """
    return _stdout(project_dir, "merge-base", ref, "HEAD") or tip


def head_branch(project_dir: Path) -> str:
    """The branch ``HEAD`` is on, or empty when it is not on one."""
    return _stdout(project_dir, "rev-parse", "--abbrev-ref", "HEAD")


def empty_tree(project_dir: Path) -> str:
    """The tree every repository starts from, before its first commit.

    Asked for rather than hardcoded: the well-known `4b825dc…` is the SHA-1
    spelling, and a SHA-256 repository has its own. Diffing against it is how a
    history shorter than the question gets answered with all of itself.
    """
    return _stdout(project_dir, "hash-object", "-t", "tree", "--stdin")


def changed_paths(
    project_dir: Path, revisions: Collection[str], pathspecs: Collection[str] = ()
) -> list[str]:
    """The paths git names when diffing ``revisions``, in the project's own terms.

    ``--relative`` asks and answers relative to the project, so a project below
    the repository root compares like with like instead of being handed
    `pkg/src/a.py` for a file it calls `src/a.py`. ``-z`` stops git from quoting
    a non-ASCII name (``"caf\\303\\251.py"``), which would then match nothing.
    ``--literal-pathspecs`` keeps every path a plain path: a name like
    ``:!src/a.py`` is otherwise read as *exclude* ``src/a.py`` and silently drops
    it from the answer, and unknown magic (``:(bad)x``) makes git fail the batch.

    No ``pathspecs`` asks about the whole tree. Passing them limits the question,
    split into command lines the operating system will accept — a snoozed legacy
    repo names tens of thousands of files, and an argument list past ARG_MAX
    fails the spawn outright, which reads as "nothing changed".
    """
    if not pathspecs:
        return _diff_names(project_dir, revisions, ())
    return [
        path
        for batch in within_argument_limits(sorted(pathspecs))
        for path in _diff_names(project_dir, revisions, batch)
    ]


def untracked_paths(project_dir: Path) -> list[str]:
    """New files git is not tracking and not ignoring, in the project's own terms.

    ``git diff`` never names an untracked path, so the file just written — the one
    most likely to carry a smell — is the file a diff-built scope cannot see.
    ``--exclude-standard`` keeps ignored files out: a build artifact is not work
    in progress. ``-z`` stops a non-ASCII name being quoted (and then matching
    nothing), and ``--literal-pathspecs`` keeps a path a plain path — the same
    guards the batched diff needs. Run inside ``project_dir``, ``ls-files`` names
    paths relative to it, matching ``--relative`` on the diffs it unites with.
    """
    named = _stdout(
        project_dir,
        "--literal-pathspecs",
        "ls-files",
        "--others",
        "--exclude-standard",
        "-z",
    )
    return [path for path in named.split("\0") if path]


def uncommitted_changes(project_dir: Path) -> list[str]:
    """The work in progress a commit-to-commit diff misses: staged and unstaged
    edits to tracked files, and brand-new untracked files.

    A bare ``git diff`` shows only unstaged changes and never an untracked path,
    so in a pre-commit hook (where the work is staged) or on a branch with a new
    module, the file under review is the file no git-derived scope would measure
    (#92). Each such mode unites its history with this set; ``dict.fromkeys``
    keeps it deduplicated with first-seen order.
    """
    staged = changed_paths(project_dir, ["--cached"])
    unstaged = changed_paths(project_dir, [])
    return list(dict.fromkeys([*staged, *unstaged, *untracked_paths(project_dir)]))


def _diff_names(
    project_dir: Path, revisions: Collection[str], pathspecs: Collection[str]
) -> list[str]:
    named = _stdout(
        project_dir,
        "--literal-pathspecs",
        "diff",
        "--name-only",
        "-z",
        "--relative",
        *revisions,
        "--",
        *pathspecs,
    )
    return [path for path in named.split("\0") if path]


def _run(project_dir: Path, *args: str) -> subprocess.CompletedProcess[str] | None:
    """``git <args>`` in the project, or ``None`` when git could not be run at all.

    Every call is handed an empty stdin: ``hash-object --stdin`` needs one, and
    no other question here reads input, so none of them can sit waiting for it.
    """
    try:
        return subprocess.run(
            ["git", *args], cwd=project_dir, capture_output=True, text=True, input=""
        )
    except OSError:
        return None


def _stdout(project_dir: Path, *args: str) -> str:
    """``git <args>`` output, or empty on any failure — the safe degrade."""
    result = _run(project_dir, *args)
    if result is None or result.returncode != 0:
        return ""
    return result.stdout.strip()

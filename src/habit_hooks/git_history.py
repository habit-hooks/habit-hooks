"""Ask git what it remembers: where a branch left its base ref, and which paths
differ since.

Two callers put the same question in the same words — a scoped run
(``scope.py``) and a lapsing snooze (``changed_files.py``) — and they differ only
in what they make of silence. The facts live here so there is one answer:
``[scope] branchBase`` cannot come to mean one thing in a run and another in a
snooze, and a flag this module gets right cannot be missing from the other
caller. Each caller keeps its own policy for the two silences: a directory git
cannot place, and a ref a real repository does not have.

What git says about the working tree *as it stands* — which files the project
holds, which of them it ignores — is ``git_listing``, asked from here only to
widen a diff with the untracked work it cannot name. How any of it is spawned is
``git_command``'s, one module further down.
"""

from __future__ import annotations

from collections.abc import Collection
from pathlib import Path

from .argv_budget import within_argument_limits
from .git_command import git, git_output, git_succeeded
from .git_listing import untracked_paths


def places_directory(project_dir: Path) -> bool:
    """Whether git can place this directory in a repository at all.

    False covers both ways git can say nothing: no repository here, and no git
    to ask. Neither is a mistake a message could help with, so each caller
    degrades rather than failing on it.
    """
    return git_succeeded(project_dir, "rev-parse", "--is-inside-work-tree")


def resolves(project_dir: Path, ref: str) -> str | None:
    """The commit ``ref`` names here, or ``None`` when this checkout has no such ref.

    Git answers a ref it never heard of with an empty diff, which reads as "this
    branch changed nothing" — a clean run over an unscanned tree.
    ``--verify --quiet`` is what tells the two apart.
    """
    verified = git(project_dir, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
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
    return git_output(project_dir, "merge-base", ref, "HEAD") or tip


def head_branch(project_dir: Path) -> str:
    """The branch ``HEAD`` is on, or empty when it is not on one."""
    return git_output(project_dir, "rev-parse", "--abbrev-ref", "HEAD")


def empty_tree(project_dir: Path) -> str:
    """The tree every repository starts from, before its first commit.

    Asked for rather than hardcoded: the well-known `4b825dc…` is the SHA-1
    spelling, and a SHA-256 repository has its own. Diffing against it is how a
    history shorter than the question gets answered with all of itself.
    """
    return git_output(project_dir, "hash-object", "-t", "tree", "--stdin")


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
    named = git_output(
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

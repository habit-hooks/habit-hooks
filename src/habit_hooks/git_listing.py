"""What git says about the working tree as it stands: which files this project
holds, and which of them it was told to forget.

The counterpart to ``git_history``, which asks what git *remembers* — refs,
merge bases, the diff between two revisions. Both spawn through ``git_command``
and neither is the other's caller's business: a scope built from history asks
here only to widen itself with untracked work, and a whole-project scan asks
here alone. Splitting them is what keeps each under the repo's own 200-line
``oversized-file`` gate, and it is the same line, in the same direction, as
``config`` → ``config_schema`` and ``part_output`` → ``diagnosis``.

Every answer degrades to empty or ``False``, never to an exception: outside a
repository and on a machine with no git, nothing here is a mistake a message
could help with. What to make of that silence is the caller's decision — and no
caller is allowed to read it as "nothing there".
"""

from __future__ import annotations

from pathlib import Path

from .git_command import git_output, git_succeeded

# What git stores a submodule mount point as. A tracked symlink is 120000 and an
# ordinary file 100644, so this one value separates a gitlink from everything.
_GITLINK_MODE = "160000 "


def ignores_directory(project_dir: Path) -> bool:
    """Whether the repository around this directory ignores the directory itself.

    A project can sit inside somebody else's ignored tree — this repository runs
    its own spec cases under a ``.spec-runs/`` its ``.gitignore`` covers, and
    each case is a real project. Every file in such a project is ignored, by a
    rule that was never about that project, so what git keeps there is nothing
    at all. A caller filtering by that answer would scope the run to zero files
    and report the lot clean, which is why it asks this first and stands down.

    ``--no-index`` is what makes this a question about the ignore rules rather
    than about the index, and it is the whole reason the guard is worth having.
    An empty answer a caller can already spot for itself; by default
    ``check-ignore`` calls a directory holding anything the outer repository
    tracks — a file force-added under an ignored path — "not ignored", so the
    guard would stand down for exactly the project whose file list comes back
    **partial**. Partial is the dangerous shape: it looks like a real answer, so
    the run scans the one force-added file and pronounces every other file clean
    without reading it.

    **A repository never ignores its own root**, and asking about it anyway is
    how the guard used to misfire. The question was ``check-ignore .``, whose
    answer for the root of a repository is whatever its own ``.gitignore`` says
    about the name ``.`` — so a file opening ``*`` and listing exceptions after
    it, the ordinary allow-list shape, reported its own project ignored and
    threw away a perfectly good file list. The root is therefore settled first,
    against ``rev-parse --show-toplevel``, and only a project *below* a
    repository root is asked about at all.

    The path is then spelled out in full rather than as ``.``: a nested project
    with an allow-list ``.gitignore`` of its own has the same ``*`` matched
    against the same ``.`` otherwise, and answers "ignored" about a directory
    the repository above it is perfectly happy with.

    False where there is no repository, and where there is no git to ask:
    nothing ignores anything then either.
    """
    if _is_a_repository_root(project_dir):
        return False
    return git_succeeded(
        project_dir, "check-ignore", "--no-index", "--quiet", "--", str(project_dir)
    )


def _is_a_repository_root(project_dir: Path) -> bool:
    """Whether this directory is the top of the repository that answers for it.

    Asked of git rather than by looking for a ``.git`` entry, so a linked
    worktree (whose ``.git`` is a file) and a ``GIT_DIR`` pointed elsewhere are
    both answered correctly. Resolved on both sides before comparing: git always
    reports a real path, and on macOS a ``/var/...`` project is ``/private/var``
    to git.
    """
    top = git_output(project_dir, "rev-parse", "--show-toplevel")
    return bool(top) and Path(top).resolve() == project_dir.resolve()


def project_files(project_dir: Path) -> list[str]:
    """Every file this project keeps: what git tracks, plus what it has just
    written and does not ignore.

    What a project ignores is not its own, and nothing else knows that as
    cheaply: a ``node_modules`` full of ``.d.ts`` would otherwise answer for what
    language a project is written in. Outside a repository — and where there is
    no git to ask — the answer is empty, the silence every question here
    degrades to.
    """
    return _listed_files(project_dir, "--cached", "--others")


def untracked_paths(project_dir: Path) -> list[str]:
    """New files git is not tracking and not ignoring, in the project's own terms.

    ``git diff`` never names an untracked path, so the file just written — the one
    most likely to carry a smell — is the file a diff-built scope cannot see.
    """
    return _listed_files(project_dir, "--others")


def submodule_paths(project_dir: Path) -> list[str]:
    """Where this project mounts other repositories, as git recorded them.

    Asked of the index, never of the filesystem. A submodule is a **gitlink**,
    which git stores with mode ``160000`` and nothing else has — so the question
    has an exact answer and needs no ``.gitmodules`` to parse.

    ``Path.is_dir()`` cannot answer it: it follows symlinks, so a *tracked
    symlink to a directory* (mode ``120000``) looks identical to a gitlink. That
    is not a corner case — a symlinked ``node_modules`` is pnpm's ordinary
    layout, so the filesystem question calls an everyday JavaScript project's
    dependency tree a submodule.

    ``ls-files --stage`` prints ``<mode> <object> <stage>\\t<path>``; ``-z``
    keeps a non-ASCII path unquoted, as everywhere else here.
    """
    listed = git_output(project_dir, "ls-files", "--stage", "-z")
    return [
        entry.split("\t", 1)[1]
        for entry in listed.split("\0")
        if entry.startswith(_GITLINK_MODE) and "\t" in entry
    ]


def _listed_files(project_dir: Path, *selectors: str) -> list[str]:
    """What ``git ls-files`` names under ``selectors``, in the project's own terms.

    ``--exclude-standard`` keeps ignored files out: a build artifact is neither
    work in progress nor source. ``-z`` stops git quoting a non-ASCII name as
    ``"caf\\303\\251.py"``, which then names nothing on disk and is silently
    dropped from the answer. Run inside ``project_dir``, ``ls-files`` names paths
    relative to it, matching the ``--relative`` on the diffs they unite with.

    No ``--literal-pathspecs`` here, unlike the batched diff: that flag governs
    how a *pathspec argument* is read, and every question asked here passes only
    selectors. Adding one means adding the flag with it.
    """
    named = git_output(
        project_dir, "ls-files", *selectors, "--exclude-standard", "-z"
    )
    return [path for path in named.split("\0") if path]

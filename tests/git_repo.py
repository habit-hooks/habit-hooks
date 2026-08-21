"""Build the small git repositories the changed-file and scope tests ask
questions about.

Every case here needs the same thing: a real repository, on a known branch, with
something committed to compare against. This module only builds those; what a
run must then conclude from them lives in ``test_changed_files.py`` and the
``test_a_scan_*`` modules.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def git(project_dir: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=project_dir, check=True, capture_output=True)


def stop_the_upward_walk_at(directory: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Git's search for a repository stops at ``directory``, so a case can only
    ever see the repository it built for itself.

    Without a ceiling, a case that shells out to git in a directory of its own
    is answered about whatever repository lies above — this checkout, when the
    case runs inside it. That is not hypothetical: a case doing exactly this
    renamed this repository's ``main`` branch while proving an unrelated point.
    """
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(directory))


def repository(project_dir: Path, ignoring: str = "") -> Path:
    """An empty repository at ``project_dir``, on ``main``, able to commit.

    A ``.gitignore`` is written only when ``ignoring`` asks for one: an empty
    file is itself a file, and would join the answer to every question about
    what this project holds.
    """
    project_dir.mkdir(parents=True, exist_ok=True)
    git(project_dir, "init", "-q", "-b", "main", ".")
    git(project_dir, "config", "user.email", "spec@example.com")
    git(project_dir, "config", "user.name", "Spec Runner")
    git(project_dir, "config", "commit.gpgsign", "false")
    if ignoring:
        (project_dir / ".gitignore").write_text(ignoring, encoding="utf-8")
    return project_dir


def repository_with_committed_file(project_dir: Path) -> Path:
    """A one-commit repository on ``main``; returns its committed file."""
    committed_file = project_dir / "src.py"
    committed_file.write_text("VALUES = [1]\n", encoding="utf-8")
    repository(project_dir)
    git(project_dir, "add", "src.py")
    git(project_dir, "commit", "-q", "-m", "baseline")
    return committed_file


def written(file: Path) -> Path:
    """A source file at ``file``, and the directories to reach it."""
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text("x = 1\n", encoding="utf-8")
    return file


def committed(project_dir: Path, file: Path) -> Path:
    """``file`` written and committed to the repository at ``project_dir``.

    ``--force`` so a case can put a file into the index that the repository's own
    rules ignore, which is a scope question all of its own.
    """
    written(file)
    git(project_dir, "add", "--force", str(file.relative_to(project_dir)))
    git(project_dir, "commit", "-q", "-m", f"add {file.name}")
    return file


def submodule(project_dir: Path, inner: Path, at: str) -> Path:
    """``inner`` checked out inside ``project_dir`` at ``at``, and committed.

    ``protocol.file.allow`` lifts git's own refusal to clone a submodule over a
    local path (CVE-2022-39253), which is the only kind of source a test has.
    """
    git(
        project_dir,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "--quiet",
        "add",
        inner.as_posix(),
        at,
    )
    git(project_dir, "commit", "-q", "-m", f"vendor {at}")
    return project_dir / at


def tracked_symlink(project_dir: Path, at: str, target: Path) -> Path:
    """A symlink at ``at`` pointing to ``target``, tracked by the repository.

    Git records one with mode ``120000``, never the ``160000`` of a submodule —
    but on disk it answers ``is_dir()`` exactly as a submodule does. A symlinked
    ``node_modules`` is pnpm's ordinary layout, so this is the everyday shape
    that any filesystem-based test for a submodule gets wrong.
    """
    link = project_dir / at
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(target)
    git(project_dir, "add", at)
    git(project_dir, "commit", "-q", "-m", f"link {at}")
    return link


def commit_file(file: Path, body: str) -> None:
    """Write ``body`` to ``file`` and commit it, in the repository it sits in."""
    file.write_text(body, encoding="utf-8")
    git(file.parent, "add", file.name)
    git(file.parent, "commit", "-q", "-m", f"change {file.name}")

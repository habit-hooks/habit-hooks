"""Build the small git repositories the changed-file tests ask questions about.

Every case here needs the same thing: a real repository, on a known branch, with
something committed to compare against. This module only builds those; what a
run must then conclude from them lives in ``test_changed_files.py``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def git(project_dir: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=project_dir, check=True, capture_output=True)


def repository_with_committed_file(project_dir: Path) -> Path:
    """A one-commit repository on ``main``; returns its committed file."""
    committed = project_dir / "src.py"
    committed.write_text("VALUES = [1]\n", encoding="utf-8")
    git(project_dir, "init", "-q", "-b", "main", ".")
    git(project_dir, "config", "user.email", "spec@example.com")
    git(project_dir, "config", "user.name", "Spec Runner")
    git(project_dir, "config", "commit.gpgsign", "false")
    git(project_dir, "add", "src.py")
    git(project_dir, "commit", "-q", "-m", "baseline")
    return committed


def commit_file(file: Path, body: str) -> None:
    """Write ``body`` to ``file`` and commit it, in the repository it sits in."""
    file.write_text(body, encoding="utf-8")
    git(file.parent, "add", file.name)
    git(file.parent, "commit", "-q", "-m", f"change {file.name}")

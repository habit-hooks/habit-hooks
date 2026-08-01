"""Unit tests for the git question behind a lapsing snooze.

These pin the safe degrade: a path git cannot place must read as "unchanged", so
a snooze holds. The executable specs run inside this repository's own checkout,
so the "no repository at all" case can only be pinned here, in a temp directory
git cannot place.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from habit_hooks.changed_files import changed_against_base


def _git(project_dir: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=project_dir, check=True, capture_output=True)


def _repo_with_committed_file(project_dir: Path) -> Path:
    """A one-commit repository on ``main``; returns its committed file."""
    committed = project_dir / "src.py"
    committed.write_text("VALUES = [1]\n")
    _git(project_dir, "init", "-q", "-b", "main", ".")
    _git(project_dir, "config", "user.email", "spec@example.com")
    _git(project_dir, "config", "user.name", "Spec Runner")
    _git(project_dir, "config", "commit.gpgsign", "false")
    _git(project_dir, "add", "src.py")
    _git(project_dir, "commit", "-q", "-m", "baseline")
    return committed


def _git_places_directory(project_dir: Path) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=project_dir,
        capture_output=True,
    )
    return result.returncode == 0


def test_no_repository_reports_nothing_changed(tmp_path: Path) -> None:
    assert not _git_places_directory(tmp_path)  # the situation under test
    assert changed_against_base(["src.py"], tmp_path, "main") == set()


def test_committed_file_is_unchanged(tmp_path: Path) -> None:
    _repo_with_committed_file(tmp_path)
    assert changed_against_base(["src.py"], tmp_path, "main") == set()


def test_only_the_edited_file_comes_back(tmp_path: Path) -> None:
    edited = _repo_with_committed_file(tmp_path)
    untouched = tmp_path / "other.py"
    untouched.write_text("VALUES = [2]\n")
    _git(tmp_path, "add", "other.py")
    _git(tmp_path, "commit", "-q", "-m", "other")
    edited.write_text("VALUES = [1, 2]\n")
    assert changed_against_base(["src.py", "other.py"], tmp_path, "main") == {"src.py"}


def test_absolute_paths_are_understood(tmp_path: Path) -> None:
    """eslint and comment report an absolute ``details.file``; git accepts those."""
    edited = _repo_with_committed_file(tmp_path)
    edited.write_text("VALUES = [1, 2]\n")
    assert changed_against_base([str(edited)], tmp_path, "main") == {str(edited)}


def test_untracked_file_reports_nothing_changed(tmp_path: Path) -> None:
    _repo_with_committed_file(tmp_path)
    (tmp_path / "new.py").write_text("VALUES = [3]\n")
    assert changed_against_base(["new.py"], tmp_path, "main") == set()


def test_path_outside_the_repository_reports_nothing_changed(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _repo_with_committed_file(project)
    (tmp_path / "outside.py").write_text("VALUES = [4]\n")
    assert changed_against_base(["../outside.py"], project, "main") == set()


def test_unresolvable_base_ref_fails_loudly(tmp_path: Path) -> None:
    """Silently answering "unchanged" here would make every snooze permanent."""
    edited = _repo_with_committed_file(tmp_path)
    edited.write_text("VALUES = [1, 2]\n")
    _git(tmp_path, "branch", "-m", "main", "trunk")
    with pytest.raises(SystemExit) as failure:
        changed_against_base(["src.py"], tmp_path, "main")
    assert "'main'" in str(failure.value)
    assert "branchBase" in str(failure.value)


def test_nothing_snoozed_asks_git_nothing(tmp_path: Path) -> None:
    """An empty index stays a true no-op, even where the base ref is broken."""
    _repo_with_committed_file(tmp_path)
    _git(tmp_path, "branch", "-m", "main", "trunk")
    assert changed_against_base([], tmp_path, "main") == set()


def _commit_change(file: Path, body: str) -> None:
    """Write ``body`` to ``file`` and commit it, in the repository it sits in."""
    file.write_text(body)
    _git(file.parent, "add", file.name)
    _git(file.parent, "commit", "-q", "-m", f"change {file.name}")


def test_a_change_on_the_base_ref_is_not_ours(tmp_path: Path) -> None:
    """Measured from the merge base, so debt this branch never touched holds."""
    ours = _repo_with_committed_file(tmp_path)
    theirs = tmp_path / "theirs.py"
    _commit_change(theirs, "VALUES = [2]\n")
    _git(tmp_path, "checkout", "-q", "-b", "feature")
    _commit_change(ours, "VALUES = [1, 2]\n")
    _git(tmp_path, "checkout", "-q", "main")
    _commit_change(theirs, "VALUES = [2, 3]\n")
    _git(tmp_path, "checkout", "-q", "feature")
    assert changed_against_base(["src.py", "theirs.py"], tmp_path, "main") == {"src.py"}


def test_a_bracketed_path_is_not_a_glob(tmp_path: Path) -> None:
    """`app/[slug]/page.tsx` must not lapse because `app/s/page.tsx` changed."""
    _repo_with_committed_file(tmp_path)
    routes = tmp_path / "app"
    (routes / "[slug]").mkdir(parents=True)
    (routes / "s").mkdir()
    (routes / "[slug]" / "page.tsx").write_text("export const dynamic = 1;\n")
    (routes / "s" / "page.tsx").write_text("export const static_ = 1;\n")
    _git(tmp_path, "add", "app")
    _git(tmp_path, "commit", "-q", "-m", "routes")
    (routes / "s" / "page.tsx").write_text("export const static_ = 2;\n")
    assert changed_against_base(["app/[slug]/page.tsx"], tmp_path, "main") == set()

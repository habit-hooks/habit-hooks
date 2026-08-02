"""Unit tests for what a lapsing snooze concludes from git.

These pin the safe degrade: a path git cannot place must read as "unchanged", so
a snooze holds, while a base ref a real repository cannot resolve must not. The
executable specs run inside this repository's own checkout, so the "no repository
at all" case can only be pinned here, in a temp directory git cannot place. How
the question is put to git is pinned next door, in ``test_git_batching.py``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from git_repo import commit_file, git, repository_with_committed_file
from habit_hooks.changed_files import changed_against_base


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
    repository_with_committed_file(tmp_path)
    assert changed_against_base(["src.py"], tmp_path, "main") == set()


def test_only_the_edited_file_comes_back(tmp_path: Path) -> None:
    edited = repository_with_committed_file(tmp_path)
    untouched = tmp_path / "other.py"
    untouched.write_text("VALUES = [2]\n")
    git(tmp_path, "add", "other.py")
    git(tmp_path, "commit", "-q", "-m", "other")
    edited.write_text("VALUES = [1, 2]\n")
    assert changed_against_base(["src.py", "other.py"], tmp_path, "main") == {"src.py"}


def test_absolute_paths_are_understood(tmp_path: Path) -> None:
    """eslint and comment report an absolute ``details.file``; git accepts those."""
    edited = repository_with_committed_file(tmp_path)
    edited.write_text("VALUES = [1, 2]\n")
    assert changed_against_base([str(edited)], tmp_path, "main") == {str(edited)}


def test_untracked_file_reports_nothing_changed(tmp_path: Path) -> None:
    repository_with_committed_file(tmp_path)
    (tmp_path / "new.py").write_text("VALUES = [3]\n")
    assert changed_against_base(["new.py"], tmp_path, "main") == set()


def test_path_outside_the_repository_reports_nothing_changed(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    repository_with_committed_file(project)
    (tmp_path / "outside.py").write_text("VALUES = [4]\n")
    assert changed_against_base(["../outside.py"], project, "main") == set()


def test_unresolvable_base_ref_fails_loudly(tmp_path: Path) -> None:
    """Silently answering "unchanged" here would make every snooze permanent."""
    edited = repository_with_committed_file(tmp_path)
    edited.write_text("VALUES = [1, 2]\n")
    git(tmp_path, "branch", "-m", "main", "trunk")
    with pytest.raises(SystemExit) as failure:
        changed_against_base(["src.py"], tmp_path, "main")
    assert "'main'" in str(failure.value)
    assert "branchBase" in str(failure.value)


def test_nothing_snoozed_asks_git_nothing(tmp_path: Path) -> None:
    """An empty index stays a true no-op, even where the base ref is broken."""
    repository_with_committed_file(tmp_path)
    git(tmp_path, "branch", "-m", "main", "trunk")
    assert changed_against_base([], tmp_path, "main") == set()


def test_a_change_on_the_base_ref_is_not_ours(tmp_path: Path) -> None:
    """Measured from the merge base, so debt this branch never touched holds."""
    ours = repository_with_committed_file(tmp_path)
    theirs = tmp_path / "theirs.py"
    commit_file(theirs, "VALUES = [2]\n")
    git(tmp_path, "checkout", "-q", "-b", "feature")
    commit_file(ours, "VALUES = [1, 2]\n")
    git(tmp_path, "checkout", "-q", "main")
    commit_file(theirs, "VALUES = [2, 3]\n")
    git(tmp_path, "checkout", "-q", "feature")
    assert changed_against_base(["src.py", "theirs.py"], tmp_path, "main") == {"src.py"}

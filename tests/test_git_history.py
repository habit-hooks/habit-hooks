"""Unit tests for the one place that asks git about a branch's history.

A scoped run and a lapsing snooze put the same question to git, so they share
one implementation ([DECISIONS.md](../docs/DECISIONS.md)); these pin what that
implementation answers, including the silences each caller then interprets
differently. How each caller phrases its failure is pinned next door, in
``test_scope.py`` and ``test_changed_files.py``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from git_repo import commit_file, git, repository_with_committed_file
from habit_hooks import git_history


def test_a_directory_no_repository_holds_is_not_placed(tmp_path: Path) -> None:
    assert git_history.places_directory(tmp_path) is False


def test_a_repository_is_placed(tmp_path: Path) -> None:
    repository_with_committed_file(tmp_path)
    assert git_history.places_directory(tmp_path) is True


def test_git_that_cannot_be_run_places_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No git on PATH must degrade like no repository, never as a traceback."""
    repository_with_committed_file(tmp_path)

    def no_git(*_args: object, **_options: object) -> object:
        raise OSError("git: command not found")

    monkeypatch.setattr(git_history.subprocess, "run", no_git)
    assert git_history.places_directory(tmp_path) is False


def test_a_known_ref_resolves_to_its_commit(tmp_path: Path) -> None:
    repository_with_committed_file(tmp_path)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True
    ).stdout.strip()
    assert git_history.resolves(tmp_path, "main") == head


def test_a_ref_this_checkout_lacks_does_not_resolve(tmp_path: Path) -> None:
    repository_with_committed_file(tmp_path)
    assert git_history.resolves(tmp_path, "nope") is None


def test_a_branch_forks_at_its_merge_base(tmp_path: Path) -> None:
    ours = repository_with_committed_file(tmp_path)
    git(tmp_path, "checkout", "-q", "-b", "feature")
    commit_file(ours, "VALUES = [1, 2]\n")
    base = git_history.resolves(tmp_path, "main")
    assert git_history.forked_at(tmp_path, "main", "unused-tip") == base


def test_histories_with_no_common_ancestor_fall_back_to_the_tip(
    tmp_path: Path,
) -> None:
    """An orphan branch shares no commit with the base, so git names no merge
    base at all — and comparing against nothing would scope a run to nothing."""
    repository_with_committed_file(tmp_path)
    git(tmp_path, "checkout", "-q", "--orphan", "unrelated")
    (tmp_path / "other.py").write_text("VALUES = [9]\n")
    git(tmp_path, "add", "other.py")
    git(tmp_path, "commit", "-q", "-m", "unrelated history")
    tip = git_history.resolves(tmp_path, "main")

    assert subprocess.run(  # the situation under test: git can name no merge base
        ["git", "merge-base", "main", "HEAD"], cwd=tmp_path, capture_output=True
    ).returncode != 0
    assert git_history.forked_at(tmp_path, "main", tip) == tip


def test_the_empty_tree_precedes_every_commit(tmp_path: Path) -> None:
    """The state a repository's whole history is measured against."""
    repository_with_committed_file(tmp_path)
    before_anything = git_history.empty_tree(tmp_path)
    assert git_history.changed_paths(tmp_path, [before_anything, "HEAD"]) == ["src.py"]


def test_no_pathspecs_asks_about_the_whole_tree(tmp_path: Path) -> None:
    edited = repository_with_committed_file(tmp_path)
    edited.write_text("VALUES = [1, 2]\n")
    assert git_history.changed_paths(tmp_path, []) == ["src.py"]


def test_paths_are_named_in_the_projects_own_terms(tmp_path: Path) -> None:
    """git answers from the repository root; a project below it asks in its own."""
    repository_with_committed_file(tmp_path)
    project = tmp_path / "app"
    project.mkdir()
    nested = project / "nested.py"
    commit_file(nested, "VALUES = [2]\n")
    nested.write_text("VALUES = [2, 3]\n")
    assert git_history.changed_paths(project, []) == ["nested.py"]


def test_a_non_ascii_path_comes_back_unquoted(tmp_path: Path) -> None:
    """Quoted (`"caf\\303\\251.py"`) it would match no file anyone can name."""
    repository_with_committed_file(tmp_path)
    accented = tmp_path / "café.py"
    commit_file(accented, "VALUES = [2]\n")
    accented.write_text("VALUES = [2, 3]\n")
    assert git_history.changed_paths(tmp_path, []) == ["café.py"]

"""Unit tests for what git says the working tree holds right now.

The counterpart to ``test_git_history.py``: these pin ``git ls-files``' answers
— which files a project keeps, and which of them the ignore rules take back —
where those pin what git remembers between two revisions. What a whole-project
scan then *does* with these answers is the ``test_a_scan_*`` modules.
"""

from __future__ import annotations

from pathlib import Path

from git_repo import repository_with_committed_file
from habit_hooks import git_listing


def test_an_untracked_file_is_named(tmp_path: Path) -> None:
    """The file `git diff` never mentions, and a scoped run must still measure."""
    repository_with_committed_file(tmp_path)
    (tmp_path / "fresh.py").write_text("VALUES = [1]\n", encoding="utf-8")
    assert git_listing.untracked_paths(tmp_path) == ["fresh.py"]


def test_an_ignored_file_is_not_named_untracked(tmp_path: Path) -> None:
    """`--exclude-standard` keeps a build artifact out of the work in progress."""
    repository_with_committed_file(tmp_path)
    (tmp_path / ".gitignore").write_text("build.py\n", encoding="utf-8")
    (tmp_path / "build.py").write_text("VALUES = [9]\n", encoding="utf-8")
    assert "build.py" not in git_listing.untracked_paths(tmp_path)

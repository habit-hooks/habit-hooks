"""Unit tests for which uncommitted work a git-derived scope measures (#92).

Every git mode is built on ``git diff``, which never names an untracked file and,
with no revision, never a staged one — so the file just written is the one a
scoped run would miss. These pin that each mode now widens its history with the
work in progress, while an ignored file still stays out. The end-to-end wiring is
shown in ``docs/habit-sensors.spec.md`` under "Git-derived scopes".
"""

from __future__ import annotations

from pathlib import Path

import pytest

from git_repo import git, repository_with_committed_file
from habit_hooks.config import Config, ScopeDefaults
from scope_probe import scoped_files


def _feature_branch_with_an_untracked_file(tmp_path: Path) -> None:
    """A feature branch off ``main`` carrying one brand-new untracked source file."""
    repository_with_committed_file(tmp_path)
    git(tmp_path, "checkout", "-q", "-b", "feature")
    (tmp_path / "new.py").write_text("VALUES = [1, 2, 3]\n", encoding="utf-8")


# Discovery is opt-in since #97, so every mode must name its source before it can
# measure what changed; these branches carry only `.py` files.
_PY = Config(files=["**/*.py"])


@pytest.mark.parametrize(
    ("argv", "config"),
    [
        (["--branch", "main"], _PY),
        (["--last", "1"], _PY),
        (["--since", "main"], _PY),
        ([], Config(files=["**/*.py"], scope=ScopeDefaults(autoBranchOffMain=True))),
    ],
)
def test_a_git_derived_scope_measures_an_untracked_file(
    argv: list[str], config: Config | None, tmp_path: Path
) -> None:
    """Every git-derived mode is built on a diff, which is blind to new files."""
    _feature_branch_with_an_untracked_file(tmp_path)
    assert "new.py" in scoped_files(argv, tmp_path, config)


def test_changed_only_measures_a_staged_file(tmp_path: Path) -> None:
    """A pre-commit hook reviews staged work; a bare ``git diff`` shows none of it."""
    committed = repository_with_committed_file(tmp_path)
    committed.write_text("VALUES = [1, 2]\n", encoding="utf-8")
    git(tmp_path, "add", "src.py")
    config = Config(files=["**/*.py"], scope=ScopeDefaults(changedOnly=True))
    assert scoped_files([], tmp_path, config) == ["src.py"]


def test_a_gitignored_untracked_file_is_not_measured(tmp_path: Path) -> None:
    """A build artifact is not work in progress, so it stays out of the scope."""
    repository_with_committed_file(tmp_path)
    git(tmp_path, "checkout", "-q", "-b", "feature")
    (tmp_path / ".gitignore").write_text("build.py\n", encoding="utf-8")
    (tmp_path / "build.py").write_text("VALUES = [9]\n", encoding="utf-8")
    config = Config(files=["**/*.py"])
    assert "build.py" not in scoped_files(["--branch", "main"], tmp_path, config)

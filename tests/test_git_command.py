"""Unit tests for the one place a git question is spawned.

Everything above this module — a scope, a lapsing snooze, a whole-project scan —
degrades on an empty answer and falls back to something safe. That only works if
an answer is empty *whenever git failed*, so this is where that is pinned: git
is perfectly capable of printing a plausible-looking line to stdout and then
exiting non-zero, and a caller reading the line would take a failure for a fact.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from git_repo import git, repository, repository_with_committed_file
from habit_hooks import git_command, git_history

# A repository with no commits yet has a HEAD pointing at an unborn branch.
# `rev-parse --abbrev-ref HEAD` cannot resolve it: it exits 128 *and* prints the
# literal string "HEAD" on stdout — a failure that looks exactly like an answer.
_UNRESOLVABLE_HEAD = ("rev-parse", "--abbrev-ref", "HEAD")


def test_a_failing_git_answers_nothing_even_when_it_printed_something(
    tmp_path: Path,
) -> None:
    """The exit code is what decides, never whether stdout came back non-empty.

    Trusting the output alone would publish "HEAD" as this repository's branch
    name. Every degrade in this tool keys off an empty answer, so a failure that
    smuggles a line through arrives as a fact nothing downstream can question.
    """
    repository(tmp_path)
    printed = git_command.git(tmp_path, *_UNRESOLVABLE_HEAD)

    assert printed is not None
    assert printed.returncode != 0
    assert printed.stdout.strip() == "HEAD"  # the situation under test
    assert git_command.git_output(tmp_path, *_UNRESOLVABLE_HEAD) == ""


def test_a_repository_with_no_commits_is_on_no_branch(tmp_path: Path) -> None:
    """What the guard above buys its caller: an unborn branch is no branch.

    ``head_branch`` documents empty as "HEAD is not on a branch", and a project
    whose first commit is still to come is exactly that. Answering "HEAD" would
    make it a branch name like any other, and one a project could match its
    ``[scope] mainBranch`` against by writing the word.
    """
    repository(tmp_path)
    assert git_history.head_branch(tmp_path) == ""


def test_a_successful_git_answers_with_what_it_printed(tmp_path: Path) -> None:
    """The other half: exit 0 means the output is the answer, stripped."""
    repository_with_committed_file(tmp_path)
    assert git_history.head_branch(tmp_path) == "main"


def test_a_detached_head_keeps_gits_own_word_for_it(tmp_path: Path) -> None:
    """"HEAD" is a real answer when git exits 0 with it, so the guard cannot be
    "reject the word HEAD" — only the exit code tells the two cases apart."""
    repository_with_committed_file(tmp_path)
    git(tmp_path, "checkout", "-q", "--detach")
    assert git_history.head_branch(tmp_path) == "HEAD"


def test_git_that_cannot_be_run_at_all_answers_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No git on the machine is the third silence, and it must not raise."""

    def no_git(*_args: object, **_options: object) -> object:
        raise OSError("git: command not found")

    monkeypatch.setattr(git_command.subprocess, "run", no_git)
    assert git_command.git(tmp_path, "status") is None
    assert git_command.git_output(tmp_path, "status") == ""

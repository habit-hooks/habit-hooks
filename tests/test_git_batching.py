"""Unit tests for how the one batched ``git diff`` is asked and answered.

``changed_against_base`` asks git about every anchored file at once. That one
question has to come back attributed: each name git prints matched against the
path that asked for it. These pin what the batching risks that a question per
file never could — an answer parsed wrongly, a path read as pathspec magic, an
argument list past what the operating system will spawn.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from git_repo import commit_file, git, repository_with_committed_file
from habit_hooks import git_command
from habit_hooks.changed_files import changed_against_base


def _recorded_diffs(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, ...]]:
    """The ``git diff`` invocations made from here on, as they are made."""
    calls: list[tuple[str, ...]] = []
    spawn = subprocess.run

    def recording_run(
        args: list[str], **spawn_options: object
    ) -> subprocess.CompletedProcess[str]:
        if "diff" in args:
            calls.append(tuple(args))
        return spawn(args, **spawn_options)

    monkeypatch.setattr(git_command.subprocess, "run", recording_run)
    return calls


def test_the_whole_set_is_one_git_question(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A spawn per file cost ~39ms, inside a tool that runs in a hook loop."""
    edited = repository_with_committed_file(tmp_path)
    untouched = tmp_path / "other.py"
    commit_file(untouched, "VALUES = [2]\n")
    edited.write_text("VALUES = [1, 2]\n", encoding="utf-8")
    diffs = _recorded_diffs(monkeypatch)

    assert changed_against_base(["src.py", "other.py"], tmp_path, "main") == {"src.py"}
    assert len(diffs) == 1


def test_two_of_three_batched_paths_come_back(tmp_path: Path) -> None:
    """One question, many answers, each attributed back to the file that asked."""
    repository_with_committed_file(tmp_path)
    for name in ("a.py", "b.py", "c.py"):
        commit_file(tmp_path / name, "VALUES = [1]\n")
    (tmp_path / "a.py").write_text("VALUES = [1, 2]\n", encoding="utf-8")
    (tmp_path / "c.py").write_text("VALUES = [1, 3]\n", encoding="utf-8")

    changed = changed_against_base(["a.py", "b.py", "c.py"], tmp_path, "main")

    assert changed == {"a.py", "c.py"}


def test_a_path_that_reads_as_pathspec_magic_is_a_plain_path(tmp_path: Path) -> None:
    """Magic in one key must not silence the rest: `:!x` excludes `x` from the
    answer, and unknown magic makes git fail the whole batch."""
    edited = repository_with_committed_file(tmp_path)
    edited.write_text("VALUES = [1, 2]\n", encoding="utf-8")

    assert changed_against_base([":!src.py", "src.py"], tmp_path, "main") == {"src.py"}
    assert changed_against_base([":(bad)x.py", "src.py"], tmp_path, "main") == {"src.py"}


def test_far_more_paths_than_one_command_line_holds(tmp_path: Path) -> None:
    """The documented way into a legacy repo snoozes everything it has, and an
    argument list that overflows fails the call — every snooze then permanent."""
    edited = repository_with_committed_file(tmp_path)
    edited.write_text("VALUES = [1, 2]\n", encoding="utf-8")
    crowd = [f"generated/module_{index:06d}.py" for index in range(30_000)]

    assert changed_against_base([*crowd, "src.py"], tmp_path, "main") == {"src.py"}


def test_a_path_outside_the_repository_hides_none_of_the_others(
    tmp_path: Path,
) -> None:
    """git refuses a whole batch over one bad path; the batch must not carry it."""
    project = tmp_path / "project"
    project.mkdir()
    edited = repository_with_committed_file(project)
    edited.write_text("VALUES = [1, 2]\n", encoding="utf-8")
    (tmp_path / "outside.py").write_text("VALUES = [4]\n", encoding="utf-8")

    changed = changed_against_base(["../outside.py", "src.py"], project, "main")

    assert changed == {"src.py"}


def test_a_non_ascii_path_is_matched_by_name(tmp_path: Path) -> None:
    """git quotes those in its output unless asked not to, and a quoted name
    matches nothing — a snooze on it would never lapse."""
    repository_with_committed_file(tmp_path)
    accented = tmp_path / "café.py"
    commit_file(accented, "VALUES = [2]\n")
    accented.write_text("VALUES = [2, 3]\n", encoding="utf-8")

    assert changed_against_base(["café.py"], tmp_path, "main") == {"café.py"}


def test_a_project_below_the_repository_root_is_understood(tmp_path: Path) -> None:
    """git names paths from the repository root; the project asks in its own."""
    repository_with_committed_file(tmp_path)
    project = tmp_path / "app"
    project.mkdir()
    nested = project / "nested.py"
    commit_file(nested, "VALUES = [2]\n")
    nested.write_text("VALUES = [2, 3]\n", encoding="utf-8")

    assert changed_against_base(["nested.py"], project, "main") == {"nested.py"}


def test_a_bracketed_path_is_not_a_glob(tmp_path: Path) -> None:
    """`app/[slug]/page.tsx` must not lapse because `app/s/page.tsx` changed."""
    repository_with_committed_file(tmp_path)
    routes = tmp_path / "app"
    (routes / "[slug]").mkdir(parents=True)
    (routes / "s").mkdir()
    (routes / "[slug]" / "page.tsx").write_text("export const dynamic = 1;\n", encoding="utf-8")
    (routes / "s" / "page.tsx").write_text("export const static_ = 1;\n", encoding="utf-8")
    git(tmp_path, "add", "app")
    git(tmp_path, "commit", "-q", "-m", "routes")
    (routes / "s" / "page.tsx").write_text("export const static_ = 2;\n", encoding="utf-8")
    assert changed_against_base(["app/[slug]/page.tsx"], tmp_path, "main") == set()

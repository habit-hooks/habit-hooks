"""Unit tests for what an empty scope says out loud.

A run that measured nothing must never be indistinguishable from a clean one, so
each way of narrowing to nothing names the setting that did it — the whole-run
notice, and the per-file one a ``--file`` hook needs. Which files a mode picks in
the first place is ``test_scope.py``.
"""

from __future__ import annotations

from pathlib import Path

from git_repo import repository, stop_the_upward_walk_at, written
from habit_hooks.config import Config
from scope_probe import scope as _scope
from scope_probe import source_file

import pytest


@pytest.fixture(autouse=True)
def _only_the_repository_the_case_built(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stop_the_upward_walk_at(tmp_path, monkeypatch)


def test_a_named_file_outside_files_is_not_scanned(tmp_path: Path) -> None:
    """``--file`` obeys the same ``[files]`` setting every other mode does."""
    (tmp_path / "pnpm-lock.yaml").write_text("lock\n", encoding="utf-8")
    scoped = _scope(["--file", "pnpm-lock.yaml"], tmp_path, Config(files=["src/**"]))
    assert scoped.files == []
    assert scoped.notices == [
        "habit-sensors: --file 'pnpm-lock.yaml' is outside [files]; nothing scanned"
    ]


def test_a_named_file_with_no_files_configured_says_none_are(tmp_path: Path) -> None:
    """The default install — ``plugins = ["generic"]``, which declares no source
    — has no ``[files]`` for the file to be outside of, so saying it is outside
    one points at a section that does not exist. Say what to write instead (#97)."""
    source_file(tmp_path)
    scoped = _scope(["--file", "src/a.py"], tmp_path, Config(files=None))
    assert scoped.files == []
    assert scoped.notices == [
        "habit-sensors: --file 'src/a.py': no [files] are configured — name what "
        "to scan in .habit-hooks/config.toml; nothing scanned"
    ]


def test_a_named_file_the_project_does_not_have_is_said_so(tmp_path: Path) -> None:
    scoped = _scope(["--file", "gone.py"], tmp_path)
    assert scoped.files == []
    assert scoped.notices == [
        "habit-sensors: --file 'gone.py' is not a file in this project; nothing scanned"
    ]


def test_a_scanned_named_file_is_not_remarked_on(tmp_path: Path) -> None:
    source_file(tmp_path)
    assert _scope(["--file", "src/a.py"], tmp_path, Config(files=["src/**"])).notices == []


def test_no_files_at_all_scans_nothing_and_says_why(tmp_path: Path) -> None:
    """No `[files]` from the project and none from its plugins is opt-in to
    nothing: a default install scans nothing, not the whole tree, and says why (#97)."""
    source_file(tmp_path)
    scoped = _scope(["--all"], tmp_path, Config(files=None))
    assert scoped.files == []
    assert scoped.notices == [
        "habit-sensors: no [files] are configured — name what to scan in "
        ".habit-hooks/config.toml; nothing scanned"
    ]


def test_a_files_that_matched_nothing_says_so(tmp_path: Path) -> None:
    """The case that was silent, and the reason it mattered.

    A project whose ``.gitignore`` covers its own source tree keeps no files git
    will name, so ``[files]`` — set, and correct — matches nothing. That scanned
    zero files and rendered ✅: a run that *measured* nothing, told apart from a
    run that *found* nothing only by this line (#88).
    """
    project = repository(tmp_path / "project", ignoring="src/\n")
    written(project / "src" / "a.py")
    scoped = _scope(["--all"], project, Config(files=["**/*.py"]))

    assert scoped.files == []
    assert scoped.notices == [
        "habit-sensors: nothing matched [files] — check it in "
        ".habit-hooks/config.toml, and whether git ignores the paths you "
        "expected; nothing scanned"
    ]

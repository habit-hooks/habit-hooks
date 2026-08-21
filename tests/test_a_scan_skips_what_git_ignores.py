"""What a whole-project scan measures: the files the project keeps, not every
file on disk (#142).

``--all`` walked the directory tree, so it measured build output, caches and
``.next/`` — while ``--last 1`` and every other git-derived mode, which ask git,
never did. One project, two universes: a real pnpm monorepo held 321 tracked
``.ts``/``.tsx`` files and 843 on disk, and its owner had to hand-write
``!**/dist/**`` into ``[files]`` before a run was usable. A default somebody has
to patch is the wrong default.

These are the cases where git's answer is the one taken. When git is the wrong
thing to ask — the project itself ignored, no repository, no git at all — the
disk still answers, and that is ``test_a_scan_git_cannot_answer_for.py``. What a
scan then *says* about a submodule it stepped over is
``test_a_scan_names_the_submodules_it_skipped.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from git_repo import committed, repository, stop_the_upward_walk_at, written
from habit_hooks.config import Config, ScopeDefaults
from scope_probe import scoped_files as _scoped_files

# Discovery is opt-in since #97: a case must name its source before any mode
# enumerates anything.
_PY_SOURCE = ["**/*.py"]


@pytest.fixture(autouse=True)
def _only_the_repository_the_case_built(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stop_the_upward_walk_at(tmp_path, monkeypatch)


def test_an_ignored_file_is_out_of_a_whole_project_scan(tmp_path: Path) -> None:
    """The bug itself: build output the project told git to forget was scanned."""
    project = repository(tmp_path / "project", ignoring="dist/\n")
    committed(project, project / "src" / "a.py")
    written(project / "dist" / "built.py")
    assert _scoped_files(["--all"], project, Config(files=_PY_SOURCE)) == ["src/a.py"]


def test_a_repository_above_the_project_still_ignores_for_it(tmp_path: Path) -> None:
    """A project in a subdirectory is governed by the repository it sits in: the
    root ``.gitignore`` decides, and git answers about the subdirectory in the
    subdirectory's own terms rather than the repository root's."""
    above = repository(tmp_path / "repo", ignoring="build/\n")
    project = above / "pkg"
    committed(above, project / "keep.py")
    written(project / "build" / "generated.py")
    assert _scoped_files(["--all"], project, Config(files=_PY_SOURCE)) == ["keep.py"]


def test_a_brand_new_untracked_file_is_still_in_scope(tmp_path: Path) -> None:
    """The file most likely to carry a fresh smell is the one just written and
    never added, so "what git keeps" has to mean tracked *and* not-yet-tracked.
    Narrowing to the index alone would be a worse bug than the one being fixed.
    """
    project = repository(tmp_path / "project", ignoring="dist/\n")
    written(project / "fresh.py")
    written(project / "dist" / "built.py")
    assert _scoped_files(["--all"], project, Config(files=_PY_SOURCE)) == ["fresh.py"]


def test_a_non_ascii_name_survives_gits_answer(tmp_path: Path) -> None:
    """``-z`` is what keeps ``café.py`` a filename: quoted back as
    ``"caf\\303\\251.py"`` it names nothing on disk and is dropped, so the file
    would silently leave the scope the moment git started answering for it."""
    project = repository(tmp_path / "project", ignoring="dist/\n")
    committed(project, project / "café.py")
    written(project / "dist" / "built.py")
    assert _scoped_files(["--all"], project, Config(files=_PY_SOURCE)) == ["café.py"]


def test_the_configured_scope_filters_as_all_does(tmp_path: Path) -> None:
    """Every mode that reaches the whole-project walk gets the same answer: a run
    with no flags at all, on the main branch, is that walk under another name."""
    project = repository(tmp_path / "project", ignoring="dist/\n")
    committed(project, project / "src" / "a.py")
    written(project / "dist" / "built.py")
    config = Config(files=_PY_SOURCE, scope=ScopeDefaults(mainBranch="main"))
    assert _scoped_files([], project, config) == ["src/a.py"]


def test_files_still_narrows_what_git_keeps(tmp_path: Path) -> None:
    """``[files]`` decides what counts as source, on top of git's answer: a
    tracked, un-ignored file the project never called source stays out."""
    project = repository(tmp_path / "project")
    committed(project, project / "src" / "a.py")
    committed(project, project / "README.md")
    assert _scoped_files(["--all"], project, Config(files=_PY_SOURCE)) == ["src/a.py"]


def test_a_file_deleted_from_the_work_tree_is_still_dropped(tmp_path: Path) -> None:
    """Git keeps naming a tracked file the work tree no longer has, and a gone
    file has no smells left — the narrowing that already dropped it must still
    run after git's answer replaces the tree walk."""
    project = repository(tmp_path / "project")
    committed(project, project / "src" / "a.py").unlink()
    assert _scoped_files(["--all"], project, Config(files=_PY_SOURCE)) == []


def test_a_project_whose_own_gitignore_starts_with_a_star(tmp_path: Path) -> None:
    """The allow-list shape — ``*`` then exceptions — is a common way to write a
    ``.gitignore``, and it used to switch this whole fix off.

    The guard asked ``check-ignore .``, and ``*`` matches the name ``.`` as
    readily as any other, so a project reported *itself* ignored and its own
    file list was thrown away for the disk walk. A repository never ignores its
    own root, so that is settled before the ignore rules are consulted at all.
    """
    project = repository(tmp_path / "project", ignoring="*\n!.gitignore\n!keep.py\n")
    committed(project, project / "keep.py")
    written(project / "dist" / "built.py")
    assert _scoped_files(["--all"], project, Config(files=_PY_SOURCE)) == ["keep.py"]


def test_a_nested_project_whose_own_gitignore_starts_with_a_star(
    tmp_path: Path,
) -> None:
    """The same pattern one directory down, where the root check cannot help.

    ``pkg`` is not a repository root, so the ignore rules really are asked — and
    asked about ``.`` they are the project's *own* ``*``, which says nothing
    about what the repository above thinks of ``pkg``. Naming the directory in
    full is what puts the question to the right pattern.
    """
    above = repository(tmp_path / "repo")
    project = above / "pkg"
    written(project / ".gitignore").write_text("*\n!keep.py\n", encoding="utf-8")
    committed(above, project / "keep.py")
    written(project / "dist" / "built.py")
    assert _scoped_files(["--all"], project, Config(files=_PY_SOURCE)) == ["keep.py"]

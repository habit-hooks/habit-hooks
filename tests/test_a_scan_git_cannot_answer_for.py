"""When a whole-project scan must not believe git, and walks the disk instead.

Since #142 a whole-project scan measures the files git says the project keeps,
rather than every file on disk. That is the right answer only where git is the
right thing to ask, and there are three places it is not: a project the
surrounding repository ignores outright, a project in no repository at all, and
a machine with no git on it. In each, git's answer is empty or partial while the
project plainly has files — so the tree walk answers instead.

The direction matters. A run that over-scans is a nuisance; a run that scans
nothing reports a whole tree clean without opening a single file, which is the
false-clean this tool exists to prevent. What a scan measures when git *can*
answer is ``test_a_scan_skips_what_git_ignores.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from git_repo import committed, git, repository, stop_the_upward_walk_at, written
from habit_hooks import git_listing, project_scan
from habit_hooks.config import Config
from scope_probe import scoped_files as _scoped_files

# Discovery is opt-in since #97: a case must name its source before any mode
# enumerates anything.
_PY_SOURCE = ["**/*.py"]


@pytest.fixture(autouse=True)
def _only_the_repository_the_case_built(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stop_the_upward_walk_at(tmp_path, monkeypatch)


def test_a_project_in_somebody_elses_ignored_tree_scans_everything(
    tmp_path: Path,
) -> None:
    """A project can sit inside a directory the repository around it ignores.

    Git then calls every file in that project ignored, because the rule covering
    the project directory covers everything beneath it. That rule was never about
    this project, so it decides nothing about it. This repository is its own
    example: its spec cases run inside a ``.spec-runs/`` its ``.gitignore``
    covers, and each case is a real project whose files are all in scope.
    """
    above = repository(tmp_path / "repo", ignoring="runs/\n")
    project = above / "runs" / "case"
    written(project / "a.py")
    assert _scoped_files(["--all"], project, Config(files=_PY_SOURCE)) == ["a.py"]


def test_one_force_tracked_file_never_becomes_an_ignored_projects_whole_scope(
    tmp_path: Path,
) -> None:
    """The case that makes the guard worth having, rather than merely harmless.

    An outer repository can track a file *under* a path it ignores, by
    force-adding it. Git then lists that one file for the project and nothing
    else. A partial list is far more dangerous than an empty one: falling back to
    the disk when git says *nothing* never catches it, so the run would measure
    one file and pronounce every other file clean without reading it.

    Asking whether the directory is ignored has to ignore the index to see this
    — by default git calls a directory holding tracked content "not ignored".
    """
    above = repository(tmp_path / "repo", ignoring="runs/\n")
    project = above / "runs" / "case"
    committed(above, project / "tracked.py")
    written(project / "unseen.py")

    assert _scoped_files(["--all"], project, Config(files=_PY_SOURCE)) == [
        "tracked.py",
        "unseen.py",
    ]


def test_the_tree_walk_spells_a_nested_path_the_way_git_does(tmp_path: Path) -> None:
    """The fallback has to be a drop-in for git's answer, separators included.

    Git names a nested file ``src/a.py`` on every platform. The walk builds its
    own string from ``os.sep``, which is a backslash on Windows — and ``\\``
    and ``/`` sort differently, so the ``sorted()`` inside ``files_in`` would
    order the same project one way from git and another from the walk. No
    caller sees the backslash itself (``scope._placed`` normalises again), so
    what is at stake is the two branches being interchangeable.

    Asserted outright rather than by comparing the branches: on a Mac ``os.sep``
    is already ``/``, so a comparison passes whether or not anything normalises
    and reads its expected answer off the host. Only the Windows leg can tell
    these apart, and this is the assertion it runs.
    """
    project = tmp_path / "project"
    written(project / "src" / "a.py")
    assert project_scan.files_in(project) == ["src/a.py"]


def test_a_project_outside_a_repository_scans_everything(tmp_path: Path) -> None:
    """No repository, so nothing ignores anything and the tree walk still answers."""
    project = tmp_path / "project"
    written(project / "a.py")
    written(project / "dist" / "built.py")
    assert _scoped_files(["--all"], project, Config(files=_PY_SOURCE)) == [
        "a.py",
        "dist/built.py",
    ]


def test_a_machine_with_no_git_scans_everything(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Git's silence never means "nothing to scan". With no git to ask, the tree
    walk answers in full — including the files a present git would have call
    ignored, because nothing is left that could say so."""
    project = repository(tmp_path / "project", ignoring="dist/\n")
    written(project / "a.py")
    written(project / "dist" / "built.py")
    monkeypatch.setenv("PATH", str(written(tmp_path / "bin" / "keep.py").parent))
    assert _scoped_files(["--all"], project, Config(files=_PY_SOURCE)) == [
        "a.py",
        "dist/built.py",
    ]


def test_a_project_with_no_files_setting_asks_git_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Discovery stays opt-in (#97), and opting out is answered before any git
    call: a default install spawns no process only to discard every path it
    named.

    All three doors are held, because each was opened separately and the third
    (``submodule_paths``, for the scope notices) was added long after the first
    two and spawned ``ls-files --stage`` over a whole monorepo index before
    deciding to scan nothing.
    """

    def _never_asked(*_args: object) -> object:
        raise AssertionError("git was asked about a project with no [files]")

    monkeypatch.setattr(git_listing, "ignores_directory", _never_asked)
    monkeypatch.setattr(git_listing, "project_files", _never_asked)
    monkeypatch.setattr(git_listing, "submodule_paths", _never_asked)
    project = repository(tmp_path / "project")
    written(project / "a.py")
    assert _scoped_files(["--all"], project, Config()) == []


def test_a_repository_git_cannot_be_asked_about_still_places_its_files(
    tmp_path: Path,
) -> None:
    """A repository whose index git refuses to read answers nothing at all, and
    that failure must degrade to the disk exactly as a missing git does — not to
    an empty scope, which would read as a clean tree."""
    project = repository(tmp_path / "project", ignoring="dist/\n")
    written(project / "a.py")
    written(project / "dist" / "built.py")
    git(project, "add", "a.py")
    (project / ".git" / "index").write_bytes(b"not an index")
    assert _scoped_files(["--all"], project, Config(files=_PY_SOURCE)) == [
        "a.py",
        "dist/built.py",
    ]

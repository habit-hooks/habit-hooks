"""Which entries in git's index are submodule mount points, and which only look
like one from the filesystem.

A submodule is a **gitlink** — another repository checked out inside this one —
and git stores it with mode ``160000``. Nothing else has that mode, so the
question has an exact answer and ``.gitmodules`` never has to be read.

``Path.is_dir()`` cannot answer it. It follows symlinks, so a tracked symlink to
a directory (mode ``120000``) is indistinguishable from a gitlink — and a
symlinked ``node_modules`` is pnpm's ordinary layout, which makes that the
common case rather than a corner. These are the cases that hold the mode
question in place.

What a scan then *says* about a submodule it recognised is
``test_a_scan_names_the_submodules_it_skipped.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from git_repo import committed, repository, stop_the_upward_walk_at, tracked_symlink, written
from habit_hooks.config import Config
from platform_probe import A_MACHINE_THAT_CAN_MAKE_A_SYMLINK
from scope_probe import scope as _scope

# Discovery is opt-in since #97: a case must name its source before any mode
# enumerates anything.
_PY_SOURCE = ["**/*.py"]


@pytest.fixture(autouse=True)
def _only_the_repository_the_case_built(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stop_the_upward_walk_at(tmp_path, monkeypatch)


def test_an_ordinary_directory_is_never_called_a_submodule(tmp_path: Path) -> None:
    """Being a directory only means gitlink for a path *git named*, and git names
    no plain directory among a project's files — empty or full of source.

    Without that, every scan of a project with a subdirectory would announce a
    submodule it does not have.
    """
    project = repository(tmp_path / "project")
    committed(project, project / "src" / "a.py")
    (project / "empty").mkdir()
    scanned = _scope(["--all"], project, Config(files=_PY_SOURCE))

    assert scanned.files == ["src/a.py"]
    assert scanned.notices == []


@A_MACHINE_THAT_CAN_MAKE_A_SYMLINK
def test_a_tracked_symlink_to_a_directory_is_not_a_submodule(tmp_path: Path) -> None:
    """The everyday shape that a filesystem test gets wrong.

    ``Path.is_dir()`` follows symlinks, so a tracked symlink to a directory
    answers it exactly as a submodule does — and a symlinked ``node_modules`` is
    pnpm's ordinary layout, the very thing #142's reporter has. Git records the
    two differently (mode ``120000`` against ``160000``), so the index is asked
    and the disk is not.

    Both directions are covered: a link pointing inside the project and one
    pointing out of it, since only the second leaves the project's own tree.
    """
    outside = tmp_path / "elsewhere"
    written(outside / "dep.py")
    project = repository(tmp_path / "project")
    committed(project, project / "src" / "a.py")
    written(project / "inside" / "b.py")
    tracked_symlink(project, "node_modules", outside)
    tracked_symlink(project, "linked_in", project / "inside")
    scanned = _scope(["--all"], project, Config(files=_PY_SOURCE))

    assert (project / "node_modules").is_dir()  # the situation under test
    assert (project / "linked_in").is_dir()
    assert scanned.notices == []


def test_a_plain_tracked_file_is_not_a_submodule(tmp_path: Path) -> None:
    """Mode ``100644``, the commonest thing in any repository, says nothing."""
    project = repository(tmp_path / "project")
    committed(project, project / "src" / "a.py")
    scanned = _scope(["--all"], project, Config(files=_PY_SOURCE))

    assert scanned.files == ["src/a.py"]
    assert scanned.notices == []



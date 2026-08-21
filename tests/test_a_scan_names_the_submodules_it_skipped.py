"""What a whole-project scan says about the submodules it cannot look inside.

A submodule is another repository checked out within this one. Git names it by
its own directory and never by the files in it, so its source leaves the scan —
rightly, since every git-derived mode was always blind to one and the submodule
gates itself in its own repository. But a scope that quietly shrinks and then
renders ✅ is the false clean this tool exists to stop, so the run names each
submodule whose files it would otherwise have measured.

These cases decide **when the line is worth printing**: it is, when the run
would otherwise have measured files inside; it is not, when ``[files]`` excluded
the directory anyway, nor when a git-derived mode's own commits never touched it.

Telling a submodule from a symlink or an ordinary directory in the first place is
``test_what_counts_as_a_submodule.py``; which files a scan measures at all is
``test_a_scan_skips_what_git_ignores.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from git_repo import committed, repository, stop_the_upward_walk_at, submodule
from habit_hooks import project_scan
from habit_hooks.config import Config
from scope_probe import scope as _scope
from scope_probe import scoped_files as _scoped_files

# Discovery is opt-in since #97: a case must name its source before any mode
# enumerates anything.
_PY_SOURCE = ["**/*.py"]


@pytest.fixture(autouse=True)
def _only_the_repository_the_case_built(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stop_the_upward_walk_at(tmp_path, monkeypatch)


def _vendoring_a_submodule(tmp_path: Path) -> Path:
    """A project with source of its own and another repository checked out at
    ``vendor/lib``, which holds source matching the same ``[files]``."""
    inner = repository(tmp_path / "lib")
    committed(inner, inner / "inner.py")
    project = repository(tmp_path / "project")
    committed(project, project / "own.py")
    submodule(project, inner, "vendor/lib")
    return project


def test_a_submodules_source_is_not_this_projects_to_scan(tmp_path: Path) -> None:
    """A submodule — another repository checked out inside this one — is named by
    git as a single directory entry, never as the files inside it.

    So its source leaves a whole-project scan, which is what every git-derived
    mode already did with it: ``git diff`` names the same lone directory and does
    not descend either. The submodule gates itself, in its own repository.
    """
    project = _vendoring_a_submodule(tmp_path)
    assert (project / "vendor" / "lib" / "inner.py").is_file()
    assert _scoped_files(["--all"], project, Config(files=_PY_SOURCE)) == ["own.py"]


def test_a_submodule_left_out_of_a_partial_scan_is_named(tmp_path: Path) -> None:
    """The dangerous shape: the scan still has plenty to measure, so it reports
    on the rest and renders ✅ — over a subtree it never opened.

    Dropping a submodule is right, but doing it silently is the false clean this
    tool exists to stop, so the run says which subtree went missing.
    """
    project = _vendoring_a_submodule(tmp_path)
    scanned = _scope(["--all"], project, Config(files=_PY_SOURCE))

    assert scanned.files == ["own.py"]
    assert scanned.notices == [
        "habit-sensors: vendor/lib is a submodule; its files are scanned in "
        "their own repository"
    ]


def test_a_submodule_is_named_even_when_it_emptied_the_scan(tmp_path: Path) -> None:
    """A project that is nothing but vendored submodules scans no file at all.

    The empty-scope notice explains a missing ``[files]`` and would say nothing
    here, because ``[files]`` is present and correct — so without this the run
    is a bare ✅ over a repository whose every source file was skipped.
    """
    inner = repository(tmp_path / "lib")
    committed(inner, inner / "inner.py")
    project = repository(tmp_path / "project")
    committed(project, project / "README.md")
    submodule(project, inner, "vendor/lib")
    scanned = _scope(["--all"], project, Config(files=_PY_SOURCE))

    assert scanned.files == []
    assert "vendor/lib is a submodule" in "\n".join(scanned.notices)


def test_a_submodule_no_files_setting_wanted_is_not_mentioned(tmp_path: Path) -> None:
    """The notice claims "your scan is smaller than you think" — so it must not
    fire where the scan is exactly the size the project asked for.

    A project excluding the directory outright loses nothing by its being
    skipped. ``!**/vendor/**`` here is the shape of the typescript plugin's own
    ``!**/node_modules/**``, which made a real run announce a gap it did not have.
    """
    project = _vendoring_a_submodule(tmp_path)
    excluded = Config(files=["**/*.py", "!**/vendor/**"])

    assert _scope(["--all"], project, excluded).notices == []
    assert _scope(["--all"], project, Config(files=_PY_SOURCE)).notices != []


def test_a_submodules_own_entry_cannot_reach_a_sensor(tmp_path: Path) -> None:
    """The entry git *does* name for a submodule is a directory on disk, and a
    sensor handed it would die opening it rather than reading a file.

    Nothing keeps it out but the narrowing to files that exist, so that is what
    this measures: ``[files]`` here matches the entry and nothing else, which
    rules the glob out as the reason. The scan still ends up with no files at
    all — never with a directory dressed as one.
    """
    project = _vendoring_a_submodule(tmp_path)
    assert "vendor/lib" in project_scan.files_in(project)
    assert (project / "vendor" / "lib").is_dir()
    assert _scoped_files(["--all"], project, Config(files=["vendor/**"])) == []




def test_a_submodule_at_a_non_ascii_path_is_still_named(tmp_path: Path) -> None:
    """``-z`` on ``ls-files --stage`` keeps ``café/lib`` a path git named.

    Quoted back as ``"caf\\303\\251/lib"`` it matches nothing the scope picked,
    so the submodule is silently never mentioned — the gap goes unannounced for
    exactly the projects whose paths are hardest to spell.
    """
    inner = repository(tmp_path / "lib")
    committed(inner, inner / "inner.py")
    project = repository(tmp_path / "project")
    committed(project, project / "own.py")
    submodule(project, inner, "café/lib")
    scanned = _scope(["--all"], project, Config(files=_PY_SOURCE))

    assert scanned.files == ["own.py"]
    assert scanned.notices == [
        "habit-sensors: café/lib is a submodule; its files are scanned in "
        "their own repository"
    ]


def test_a_git_mode_is_silent_about_a_submodule_it_never_touched(
    tmp_path: Path,
) -> None:
    """A scoped run answers about what changed, so a submodule its commits never
    moved is not something it left out.

    Without that, every ``--last 1`` in a repository with a submodule would
    announce it — on a pre-commit hook, on every commit, for ever.
    """
    project = _vendoring_a_submodule(tmp_path)
    committed(project, project / "later.py")
    scanned = _scope(["--last", "1"], project, Config(files=_PY_SOURCE))

    assert scanned.files == ["later.py"]
    assert scanned.notices == []

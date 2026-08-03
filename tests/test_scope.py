"""Unit tests for what a run decides is in scope.

The modes a consumer meets are pinned end to end in the executable specs
(``docs/habit-sensors.spec.md``). These cover what is awkward to show there: the
diagnosis each flag gives for a ref its checkout does not have, and the
precedence between "no repository" and "no such ref". The specs run inside this
repository's own checkout, so the no-repository case can only be pinned here.
What an empty scope says out loud is ``test_scope_notices.py``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from git_repo import commit_file, git, repository_with_committed_file
from habit_hooks.config import Config, ScopeDefaults
from scope_probe import scoped_files as _scoped_files
from scope_probe import source_file as _source_file

# Discovery is opt-in since #97: a git-mode test must name its source first.
_PY_SOURCE = ["**/*.py"]


def test_no_repository_outranks_a_missing_ref(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as failure:
        _scoped_files(["--branch", "main"], tmp_path)
    assert "not a git repository" in str(failure.value)


def test_an_unresolvable_since_ref_names_the_flag(tmp_path: Path) -> None:
    repository_with_committed_file(tmp_path)
    with pytest.raises(SystemExit) as failure:
        _scoped_files(["--since", "nope"], tmp_path)
    assert "'nope'" in str(failure.value)
    assert "--since" in str(failure.value)


def test_an_unresolvable_branch_base_names_the_flag(tmp_path: Path) -> None:
    repository_with_committed_file(tmp_path)
    with pytest.raises(SystemExit) as failure:
        _scoped_files(["--branch", "nope"], tmp_path)
    assert "'nope'" in str(failure.value)
    assert "--branch" in str(failure.value)


def test_a_history_shorter_than_last_scans_everything_committed(
    tmp_path: Path,
) -> None:
    """A count is not a ref: fewer commits than asked for means "everything so far"."""
    edited = repository_with_committed_file(tmp_path)  # one commit
    commit_file(edited, "VALUES = [1, 2]\n")  # two
    assert _scoped_files(["--last", "5"], tmp_path, Config(files=_PY_SOURCE)) == [
        "src.py"
    ]


def test_last_scopes_to_the_commits_it_names(tmp_path: Path) -> None:
    repository_with_committed_file(tmp_path)
    later = tmp_path / "later.py"
    commit_file(later, "VALUES = [2]\n")
    assert _scoped_files(["--last", "1"], tmp_path, Config(files=_PY_SOURCE)) == [
        "later.py"
    ]


def test_since_scopes_to_what_changed_after_a_commit(tmp_path: Path) -> None:
    edited = repository_with_committed_file(tmp_path)
    first = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True
    ).stdout.strip()
    commit_file(edited, "VALUES = [1, 2]\n")
    assert _scoped_files(["--since", first], tmp_path, Config(files=_PY_SOURCE)) == [
        "src.py"
    ]


def test_the_configured_branch_base_must_resolve(tmp_path: Path) -> None:
    """The default path a CI checkout takes: an empty scope would read as clean."""
    repository_with_committed_file(tmp_path)
    git(tmp_path, "branch", "-m", "main", "trunk")
    git(tmp_path, "checkout", "-q", "-b", "feature")
    config = Config(scope=ScopeDefaults(autoBranchOffMain=True))
    with pytest.raises(SystemExit) as failure:
        _scoped_files([], tmp_path, config)
    assert "'main'" in str(failure.value)
    assert "branchBase" in str(failure.value)


def test_a_deleted_file_leaves_the_changed_only_scope(tmp_path: Path) -> None:
    committed = repository_with_committed_file(tmp_path)
    committed.unlink()
    config = Config(files=_PY_SOURCE, scope=ScopeDefaults(changedOnly=True))
    assert _scoped_files([], tmp_path, config) == []


def test_a_named_file_inside_files_is_scanned(tmp_path: Path) -> None:
    _source_file(tmp_path)
    scoped = _scoped_files(["--file", "src/a.py"], tmp_path, Config(files=["src/**"]))
    assert scoped == ["src/a.py"]


def test_an_absolute_named_file_is_placed_in_the_project(tmp_path: Path) -> None:
    """Editor and agent hooks hand out absolute paths (#55); a raw one matches
    no relative glob, so the whole run would scan nothing and report clean."""
    absolute = str(_source_file(tmp_path))
    scoped = _scoped_files(["--file", absolute], tmp_path, Config(files=["src/**"]))
    assert scoped == ["src/a.py"]


def test_a_roundabout_named_file_is_placed_in_the_project(tmp_path: Path) -> None:
    _source_file(tmp_path)
    scoped = _scoped_files(["--file", "src/../src/a.py"], tmp_path, Config(files=["src/**"]))
    assert scoped == ["src/a.py"]


def test_a_project_below_the_repository_root_scopes_its_own_paths(
    tmp_path: Path,
) -> None:
    """git answers from the repository root, so `pkg/src/a.py` would be looked
    for under the project and found nowhere — an empty scope, reported clean."""
    repository_with_committed_file(tmp_path)
    project = tmp_path / "pkg"
    project.mkdir()
    nested = project / "nested.py"
    commit_file(nested, "VALUES = [2]\n")
    nested.write_text("VALUES = [2, 3]\n")
    config = Config(files=_PY_SOURCE, scope=ScopeDefaults(changedOnly=True))
    assert _scoped_files([], project, config) == ["nested.py"]


def test_a_non_ascii_path_reaches_the_sensors(tmp_path: Path) -> None:
    """git quotes such a name unless told not to, and no file answers to that."""
    repository_with_committed_file(tmp_path)
    accented = tmp_path / "café.py"
    commit_file(accented, "VALUES = [2]\n")
    accented.write_text("VALUES = [2, 3]\n")
    config = Config(files=_PY_SOURCE, scope=ScopeDefaults(changedOnly=True))
    assert _scoped_files([], tmp_path, config) == ["café.py"]


def test_an_empty_files_list_scans_nothing(tmp_path: Path) -> None:
    """`files = []` is a project saying its source is nothing, like `transformers = []`."""
    _source_file(tmp_path)
    assert _scoped_files(["--all"], tmp_path, Config(files=[])) == []


def test_explicit_files_reaches_inside_a_vendor_directory(tmp_path: Path) -> None:
    """Opt-in is exact: a project may name any path as source, including one a
    convention would otherwise exclude — ``[files]`` is the only authority (#97)."""
    vendored = tmp_path / "node_modules" / "kept"
    vendored.mkdir(parents=True)
    (vendored / "keep.py").write_text("x = 1\n")
    (tmp_path / "node_modules" / "other.py").write_text("y = 2\n")
    scoped = _scoped_files(["--all"], tmp_path, Config(files=["node_modules/kept/**"]))
    assert scoped == ["node_modules/kept/keep.py"]

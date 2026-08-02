"""Unit tests for what a run decides is in scope.

The modes a consumer meets are pinned end to end in the executable specs
(``docs/habit-sensors.spec.md``). These cover what is awkward to show there: the
diagnosis each flag gives for a ref its checkout does not have, and the
precedence between "no repository" and "no such ref". The specs run inside this
repository's own checkout, so the no-repository case can only be pinned here.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from git_repo import commit_file, git, repository_with_committed_file
from habit_hooks.config import Config, ScopeDefaults
from habit_hooks.scope import Scope, parse_args, resolve_scope


def _scope(
    argv: list[str], project_dir: Path, config: Config | None = None
) -> Scope:
    return resolve_scope(parse_args(argv), config or Config(), project_dir)


def _scoped_files(
    argv: list[str], project_dir: Path, config: Config | None = None
) -> list[str]:
    return _scope(argv, project_dir, config).files


def _source_file(project_dir: Path) -> Path:
    """A source file at ``src/a.py``, returned by its absolute path."""
    (project_dir / "src").mkdir(exist_ok=True)
    source = project_dir / "src" / "a.py"
    source.write_text("x = 1\n")
    return source


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
    assert _scoped_files(["--last", "5"], tmp_path) == ["src.py"]


def test_last_scopes_to_the_commits_it_names(tmp_path: Path) -> None:
    repository_with_committed_file(tmp_path)
    later = tmp_path / "later.py"
    commit_file(later, "VALUES = [2]\n")
    assert _scoped_files(["--last", "1"], tmp_path) == ["later.py"]


def test_since_scopes_to_what_changed_after_a_commit(tmp_path: Path) -> None:
    edited = repository_with_committed_file(tmp_path)
    first = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True
    ).stdout.strip()
    commit_file(edited, "VALUES = [1, 2]\n")
    assert _scoped_files(["--since", first], tmp_path) == ["src.py"]


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
    config = Config(scope=ScopeDefaults(changedOnly=True))
    assert _scoped_files([], tmp_path, config) == []


def test_a_named_file_outside_files_is_not_scanned(tmp_path: Path) -> None:
    """``--file`` obeys the same ``[files]`` setting every other mode does."""
    (tmp_path / "pnpm-lock.yaml").write_text("lock\n")
    scoped = _scope(["--file", "pnpm-lock.yaml"], tmp_path, Config(files=["src/**"]))
    assert scoped.files == []
    assert scoped.notices == [
        "habit-sensors: --file 'pnpm-lock.yaml' is outside [files]; nothing scanned"
    ]


def test_a_named_file_the_project_does_not_have_is_said_so(tmp_path: Path) -> None:
    scoped = _scope(["--file", "gone.py"], tmp_path)
    assert scoped.files == []
    assert scoped.notices == [
        "habit-sensors: --file 'gone.py' is not a file in this project; nothing scanned"
    ]


def test_a_scanned_named_file_is_not_remarked_on(tmp_path: Path) -> None:
    _source_file(tmp_path)
    assert _scope(["--file", "src/a.py"], tmp_path, Config(files=["src/**"])).notices == []


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
    config = Config(scope=ScopeDefaults(changedOnly=True))
    assert _scoped_files([], project, config) == ["nested.py"]


def test_a_non_ascii_path_reaches_the_sensors(tmp_path: Path) -> None:
    """git quotes such a name unless told not to, and no file answers to that."""
    repository_with_committed_file(tmp_path)
    accented = tmp_path / "café.py"
    commit_file(accented, "VALUES = [2]\n")
    accented.write_text("VALUES = [2, 3]\n")
    config = Config(scope=ScopeDefaults(changedOnly=True))
    assert _scoped_files([], tmp_path, config) == ["café.py"]


def test_an_empty_files_list_scans_nothing(tmp_path: Path) -> None:
    """`files = []` is a project saying its source is nothing, like `transformers = []`."""
    _source_file(tmp_path)
    assert _scoped_files(["--all"], tmp_path, Config(files=[])) == []


def test_no_files_at_all_scans_everything(tmp_path: Path) -> None:
    """No opinion from the project and none from its plugins: scan the tree."""
    _source_file(tmp_path)
    assert _scoped_files(["--all"], tmp_path, Config(files=None)) == ["src/a.py"]

"""Unit tests for the project's own names for things: its paths, and its tools.

The spec cases cover what a sensor sees; these cover the two things a spec
cannot reach — the shapes a path arrives in, and a project reached through a
symlink, which is how a macOS temp directory (and many a CI checkout) is reached.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from habit_hooks import host_platform
from habit_hooks.project_paths import project_relative, tool_search_path, venv_bin_dir


def test_an_absolute_path_inside_the_project_is_re_expressed(tmp_path: Path) -> None:
    assert project_relative(str(tmp_path / "src" / "a.py"), tmp_path) == "src/a.py"


def test_a_relative_path_keeps_its_meaning_and_loses_its_detours(
    tmp_path: Path,
) -> None:
    assert project_relative("./src/../src/a.py", tmp_path) == "src/a.py"


def test_the_project_itself_is_not_a_path_under_it(tmp_path: Path) -> None:
    """As a key it would stand for every file at once; as a pathspec, match them."""
    assert project_relative("", tmp_path) is None
    assert project_relative(".", tmp_path) is None
    assert project_relative(str(tmp_path), tmp_path) is None


def test_a_path_escaping_the_project_cannot_be_anchored(tmp_path: Path) -> None:
    assert project_relative("../elsewhere/a.py", tmp_path) is None
    assert project_relative("/etc/hosts", tmp_path) is None


def test_a_project_reached_through_a_symlink_still_anchors(tmp_path: Path) -> None:
    """The tool resolved the path; the project did not. Both name one file."""
    real = tmp_path / "real"
    real.mkdir()
    through_link = tmp_path / "link"
    through_link.symlink_to(real)

    assert project_relative(str(real / "src" / "a.py"), through_link) == "src/a.py"


def test_a_symlinked_source_directory_keeps_the_project_s_own_name_for_it(
    tmp_path: Path,
) -> None:
    """The lexical answer wins when there is one, so a monorepo's linked source
    tree stays the path the project (and git) knows it by."""
    shared = tmp_path / "shared-lib"
    shared.mkdir()
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "shared").symlink_to(shared)

    assert project_relative("src/shared/a.py", tmp_path) == "src/shared/a.py"


def test_the_project_s_own_tool_bins_come_first_on_its_search_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A project's pinned tools beat the machine's, and one answer serves both
    the run that spawns them and the setup that reports them missing."""
    monkeypatch.setenv("PATH", "/usr/bin")

    assert tool_search_path(tmp_path).split(os.pathsep) == [
        str(tmp_path / "node_modules" / ".bin"),
        str(tmp_path / ".venv" / "bin"),
        "/usr/bin",
    ]


def test_a_venv_keeps_its_executables_under_bin(tmp_path: Path) -> None:
    """CPython's own layout, everywhere except Windows."""
    assert venv_bin_dir(tmp_path / ".venv") == tmp_path / ".venv" / "bin"


def test_a_windows_venv_keeps_its_executables_under_scripts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(host_platform, "is_windows", lambda: True)

    assert venv_bin_dir(tmp_path / ".venv") == tmp_path / ".venv" / "Scripts"


def test_the_search_path_reaches_a_windows_venv_s_scripts_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Asked through ``tool_search_path`` rather than directly — proof the two
    do not drift apart, since a run and a missing-tools report both go through
    ``tool_search_path``, never ``venv_bin_dir`` alone."""
    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.setattr(host_platform, "is_windows", lambda: True)

    entries = tool_search_path(tmp_path).split(os.pathsep)

    assert str(tmp_path / ".venv" / "Scripts") in entries
    assert str(tmp_path / ".venv" / "bin") not in entries

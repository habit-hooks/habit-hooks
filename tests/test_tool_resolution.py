"""Which file this project runs for a bare command name.

Setting a project up clears a tool by looking its name up along the project's
own search path; a run then spawns it. Those were two separate lookups until
they disagreed — Windows' own spawn adds ``.exe`` to a bare name and nothing
else, where a lookup adds every extension the machine runs, so ``jscpd`` and
``pmd``, installed as a ``.cmd`` shim and a ``.bat``, are cleared by the setup
and then reported missing by whatever spawns them by name.

One lookup now answers both (``project_paths.tool_executable``). That a spawn
carries its answer is ``test_spawned_program.py``; where the search path itself
comes from is ``test_project_paths.py``.
"""

from __future__ import annotations

import stat
from pathlib import Path

import pytest
from bare_machine import machine_bin, project_with_no_tools
from executable_stub import write_stub
from platform_probe import (
    A_MACHINE_THAT_DOES_NOT,
    A_MACHINE_THAT_SPELLS_A_COMMAND_ITSELF,
    off_windows,
)

from habit_hooks import project_paths
from habit_hooks.detectors import COMMAND_KIND, Detector
from habit_hooks.missing_tools import missing_tools
from habit_hooks.project_paths import tool_executable

JSCPD = Detector(name="jscpd", kind=COMMAND_KIND, install="npm i -D jscpd")


def test_a_command_nowhere_on_the_search_path_names_no_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = project_with_no_tools(tmp_path, monkeypatch)

    assert tool_executable("jscpd", project) is None


def test_a_command_in_the_project_s_own_bin_names_the_file_installed_there(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``.venv/bin`` is the POSIX half of the search path, so this pins off
    Windows rather than installing into a directory it would not look in."""
    project = project_with_no_tools(tmp_path, monkeypatch)
    off_windows(monkeypatch)
    bin_dir = project / ".venv" / "bin"
    write_stub(bin_dir, "jscpd")

    found = tool_executable("jscpd", project)

    assert found is not None
    assert Path(found).parent == bin_dir


def test_the_project_s_own_bin_wins_over_the_same_command_on_the_machine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The whole point of a search path of its own: a project measures with the
    versions it pinned, not with whatever the machine carries. Naming a file
    instead of a name must not hand that decision back to the machine."""
    project = project_with_no_tools(tmp_path, monkeypatch)
    write_stub(machine_bin(tmp_path), "jscpd")
    pinned = project / "node_modules" / ".bin"
    write_stub(pinned, "jscpd")

    assert Path(tool_executable("jscpd", project) or "").parent == pinned


def test_installing_a_tool_answers_the_setup_and_the_run_in_one_move(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both sides of the tool question, across the one transition that matters:
    the install that stops the setup reporting a tool missing is the very one
    that gives a run a file to spawn. A setup clearing a tool the run then
    cannot find is the support question setting a project up exists to end, and
    it cannot happen while one lookup answers both."""
    project = project_with_no_tools(tmp_path, monkeypatch)

    assert missing_tools([JSCPD], project) == (JSCPD,)
    assert tool_executable("jscpd", project) is None

    bin_dir = project / "node_modules" / ".bin"
    write_stub(bin_dir, "jscpd")

    assert missing_tools([JSCPD], project) == ()
    assert Path(tool_executable("jscpd", project) or "").parent == bin_dir


def test_a_command_found_in_this_process_s_own_directory_is_named_absolutely(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Windows' lookup searches the running process's own directory first, as
    ``cmd.exe`` does, and answers relatively when it wins there — the one shape
    the machine's own rule produces that this has to finish itself. A run
    spawns in the project instead, where the same relative name would mean a
    different file, or none. The lookup is stood in for because only Windows
    produces that answer, and what is under test is what is done with it.
    """
    project = project_with_no_tools(tmp_path, monkeypatch)
    monkeypatch.setattr(project_paths.shutil, "which", lambda *_, **__: "./jscpd.cmd")

    assert tool_executable("jscpd", project) == str(Path.cwd() / "jscpd.cmd")


@A_MACHINE_THAT_SPELLS_A_COMMAND_ITSELF
def test_a_shim_answers_to_the_bare_name_it_was_installed_under(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """npm installs every Node tool as a ``.cmd`` shim — which is why a stub
    here is one too — and the name a sensor spells is the bare one. Windows'
    own rule is what makes those one command, so this runs where that rule is."""
    project = project_with_no_tools(tmp_path, monkeypatch)
    write_stub(project / "node_modules" / ".bin", "jscpd")

    found = tool_executable("jscpd", project)

    assert found is not None
    assert found.lower().endswith("jscpd.cmd")


@A_MACHINE_THAT_DOES_NOT
def test_a_shim_named_for_windows_is_no_command_at_all_here(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other half of that rule: everywhere else a command is exactly the
    filename it is. Asking for the shim by its own name finds it, so the
    ``None`` is about the spelling and not about a tool nobody installed."""
    project = project_with_no_tools(tmp_path, monkeypatch)
    shim = project / "node_modules" / ".bin" / "jscpd.cmd"
    shim.parent.mkdir(parents=True)
    shim.write_text("@echo off\r\nexit /b 0\r\n", encoding="utf-8")
    shim.chmod(shim.stat().st_mode | stat.S_IEXEC)

    assert tool_executable("jscpd", project) is None
    assert tool_executable("jscpd.cmd", project) == str(shim)

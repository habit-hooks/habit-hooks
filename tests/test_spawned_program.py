"""Which program a spawn actually starts, given a part's argv.

The argv reaching the spawn is already built (``test_argv_parts.py``); this is
the one element the spawn does not take at face value. A bare command name is
still a name, and left as one it is found by whatever rule the platform spawns
by — which on Windows is not the rule the tool was cleared by, so a tool
sitting in the project's own bin comes back as one nobody installed. The name
is turned into a file here instead, by the lookup that cleared it
(``test_tool_resolution.py``), and only ever the program: everything else in an
argv is an argument, whatever it looks like.

No sensor habit-hooks ships spells a wrapped tool as its own ``argv[0]`` — each
runs a helper that spawns its tool itself — so what is guarded here is the
invariant, and the sensor somebody else writes the obvious way.
"""

from __future__ import annotations

import stat
import sys
from pathlib import Path

import pytest
from bare_machine import project_with_no_tools
from executable_stub import write_stub
from platform_probe import (
    A_MACHINE_THAT_DOES_NOT,
    A_MACHINE_THAT_SPELLS_A_COMMAND_ITSELF,
    off_windows,
)

from habit_hooks.sensors.spawn import Spawner


@A_MACHINE_THAT_DOES_NOT
def test_a_bare_command_is_spawned_as_the_file_the_search_path_holds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The spawn carries the file, not a name still to be found. What runs is
    settled where the search path is, and the argv the child was started with
    is what says which file that was."""
    project = project_with_no_tools(tmp_path, monkeypatch)
    off_windows(monkeypatch)
    bin_dir = project / ".venv" / "bin"
    write_stub(bin_dir, "jscpd")

    result = Spawner(project).run(["jscpd", "--reporters", "json"])

    assert result.args == [str(bin_dir / "jscpd"), "--reporters", "json"]


@A_MACHINE_THAT_SPELLS_A_COMMAND_ITSELF
def test_a_shim_the_spawn_could_not_have_found_by_name_still_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The rule itself, on the machine that has it: every Node tool a plugin
    wraps is installed as a ``.cmd`` shim, and a spawn handed the bare name adds
    ``.exe`` and nothing else, so the tool is spawnable only by its file."""
    project = project_with_no_tools(tmp_path, monkeypatch)
    bin_dir = project / "node_modules" / ".bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "jscpd.cmd").write_text("@echo off\r\necho []\r\n", encoding="utf-8")

    result = Spawner(project).run(["jscpd"])

    assert result.returncode == 0
    assert result.stdout.strip() == "[]"


@A_MACHINE_THAT_DOES_NOT
def test_a_program_named_by_a_path_is_left_for_the_spawn_to_find(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A path is not a name to look up, and looking one up would answer about
    the wrong directory: a relative path means the directory the command runs
    in — the project — while a lookup reads it against wherever this process
    happens to be. Pinned to a host that runs a shebang, which is what makes a
    stub runnable by a path at all.
    """
    project = project_with_no_tools(tmp_path, monkeypatch)
    tool = project / "tools" / "probe"
    tool.parent.mkdir(parents=True)
    tool.write_text("#!/bin/sh\nprintf '[]'\n", encoding="utf-8")
    tool.chmod(tool.stat().st_mode | stat.S_IEXEC)

    result = Spawner(project).run(["tools/probe"])

    assert result.args == ["tools/probe"]
    assert result.stdout == "[]"


def test_every_argument_after_the_program_is_spawned_exactly_as_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``${dir}/helper.py`` is a file a tool is being handed, not a command —
    it is on no search path and nothing made it executable, so a lookup would
    find nothing and call the sensor's own helper a missing tool."""
    project = project_with_no_tools(tmp_path, monkeypatch)
    script = project / "probe.py"
    script.write_text("print('[]')\n", encoding="utf-8")

    result = Spawner(project).run([sys.executable, str(script)])

    assert result.args == [sys.executable, str(script)]
    assert result.stdout.strip() == "[]"


def test_a_command_nobody_installed_in_a_project_that_is_gone_names_the_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both wrong at once is still the broken run, and it has to say so.

    A name reaching no file is left for the spawn to fail on rather than
    refused up here, so what the failure names is the checkout that is gone —
    not the tool, which would send the reader off to install something that
    was never the problem.
    """
    project = project_with_no_tools(tmp_path, monkeypatch)

    with pytest.raises(FileNotFoundError) as refusal:
        Spawner(project / "deleted").run(["jscpd"])

    assert "deleted" in str(refusal.value)
    assert "jscpd" not in str(refusal.value)

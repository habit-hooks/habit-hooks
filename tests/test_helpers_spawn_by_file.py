"""How a plugin's own helper spawns the third-party tool it wraps.

No sensor habit-hooks ships names its wrapped tool as a part's ``argv[0]``: each
runs a helper script, and the helper spawns ``jscpd``, ``pmd``, ``php`` or
``deptry`` itself. So the core resolving a part's program settles nothing for
them — the tools that actually go missing on Windows go missing one process
further in, which is why ``sensors/tool_spawn.py`` sits beside each helper.

It is a copy in each plugin because each plugin is a separately installable
distribution declaring no dependency on ``habit-hooks``: a helper cannot import
the core, and four copies beat a dependency that does not exist. What keeps four
copies honest is the first case here — they are one file, byte for byte, so
whichever of them is exercised below answers for all of them.

The lookup is not a second answer to the core's: habit-hooks hands a helper a
``PATH`` of the project's own bins (``sensors/spawn._path_env``), so
``shutil.which`` inside the helper asks exactly what ``missing_tools`` asked
when it cleared the tool. What it adds is the spelling, and which filenames a
machine runs for a bare name is that machine's own rule, reached through no seam
of ours — so the two halves of that story are pinned to hosts, as
``test_tool_resolution.py`` pins the core's.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest
from executable_stub import write_batch_stub, write_stub
from platform_probe import (
    A_MACHINE_THAT_DOES_NOT,
    A_MACHINE_THAT_SPELLS_A_COMMAND_ITSELF,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGINS = ("generic", "java", "php", "python")


def _copy(plugin: str) -> Path:
    package = REPO_ROOT / "plugins" / plugin / "src" / f"habit_hooks_{plugin}"
    return package / "sensors" / "tool_spawn.py"


def _loaded(plugin: str) -> ModuleType:
    """One plugin's copy, loaded the way its helper's own ``import`` loads it.

    Under a name of its own: all four are called ``tool_spawn``, since each is
    imported from beside the helper that uses it, and a shared suite must not
    have one of them shadow another in ``sys.modules``.
    """
    spec = importlib.util.spec_from_file_location(f"tool_spawn_{plugin}", _copy(plugin))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def tool_spawn() -> ModuleType:
    """The copy the cases below drive, standing for all four by sameness."""
    return _loaded("generic")


@pytest.fixture
def bin_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A search path holding nothing, as habit-hooks would have handed it over.

    Emptied down to one directory so a machine that happens to have the real
    tool on it cannot answer a case instead of the case answering itself.
    """
    tools = tmp_path / "project-bin"
    tools.mkdir()
    monkeypatch.setenv("PATH", str(tools))
    return tools


def test_every_plugin_carries_the_same_copy() -> None:
    """Four copies, one file. Nothing stops them drifting except this."""
    bodies = {_copy(plugin).read_bytes() for plugin in PLUGINS}

    assert len(bodies) == 1


def test_a_tool_on_the_search_path_is_spawned_as_the_file_it_is(
    tool_spawn: ModuleType, bin_dir: Path
) -> None:
    """What runs is settled where the search path is, and the argv the child was
    started with is what says which file that was — the same move the core makes
    for a part's own program, one process further in."""
    write_stub(bin_dir, "probe")

    result = tool_spawn.run_tool(["probe", "--json"])

    assert result.returncode == 0
    assert Path(result.args[0]).parent == bin_dir
    assert result.args[1:] == ["--json"]


def test_a_name_reaching_no_file_is_spawned_as_it_stands(
    tool_spawn: ModuleType, bin_dir: Path
) -> None:
    """A tool nobody installed must still fail the one way every helper already
    answers for — the ``FileNotFoundError`` each turns into the shell's own
    ``<tool>: command not found``. Resolving must not become a second way to be
    missing, with a second message nothing downstream recognises."""
    assert not list(bin_dir.iterdir())

    with pytest.raises(FileNotFoundError):
        tool_spawn.run_tool(["probe", "--json"])


def test_a_batch_file_is_never_handed_an_argument_its_shell_would_read(
    tool_spawn: ModuleType, bin_dir: Path
) -> None:
    """PMD ships ``pmd.bat`` and npm installs ``.cmd`` shims, and a helper hands
    them the scoped paths — which come out of somebody else's branch. It comes
    back as the failed run every other broken spawn is, never as a raise: a
    helper that tracebacks is the first-contact failure #114 was about."""
    write_batch_stub(bin_dir, "probe")

    result = tool_spawn.run_tool(["probe.cmd", "src/a&echo.>PWNED&.py"])

    assert result.returncode != 0
    assert result.stdout == ""
    assert "cannot pass 'src/a&echo.>PWNED&.py' to a batch file" in result.stderr
    assert not (bin_dir / "PWNED").exists()


def test_a_batch_file_still_runs_when_its_arguments_are_only_text(
    tool_spawn: ModuleType, bin_dir: Path
) -> None:
    """The refusal costs a Windows project nothing it had: the shims are how its
    tools are installed, and ordinary arguments still reach them."""
    tool = write_batch_stub(bin_dir, "probe")

    result = tool_spawn.run_tool(["probe.cmd", "--max", "200"])

    assert result.returncode == 0
    assert result.args == [str(tool), "--max", "200"]


@A_MACHINE_THAT_SPELLS_A_COMMAND_ITSELF
def test_a_shim_answers_to_the_bare_name_a_helper_spells(
    tool_spawn: ModuleType, bin_dir: Path
) -> None:
    """The rule itself, on the machine that has it. A helper spells the bare
    ``jscpd``; npm installed ``jscpd.CMD``; Windows' own spawn adds ``.exe`` and
    nothing else, so the file is reachable only by looking it up first."""
    tool = write_batch_stub(bin_dir, "probe")

    result = tool_spawn.run_tool(["probe"])

    assert result.args[0].lower() == str(tool).lower()


@A_MACHINE_THAT_DOES_NOT
def test_a_shim_named_for_windows_is_no_command_at_all_here(
    tool_spawn: ModuleType, bin_dir: Path
) -> None:
    """The other half: everywhere else a command is exactly the filename it is,
    so the bare name reaches nothing and the spawn fails as it always did. The
    file is found by its own name, so this is about the spelling and not about a
    directory the lookup never read."""
    tool = write_batch_stub(bin_dir, "probe")

    with pytest.raises(FileNotFoundError):
        tool_spawn.run_tool(["probe"])

    assert tool_spawn.run_tool(["probe.cmd"]).args[0] == str(tool)

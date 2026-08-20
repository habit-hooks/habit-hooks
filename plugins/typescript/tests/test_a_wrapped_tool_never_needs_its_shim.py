"""A tool this plugin wraps is spawned as its own script, never as its bin shim.

npm installs a Node CLI on Windows as a ``.cmd`` shim, and Node has refused to
spawn a ``.cmd`` or ``.bat`` since its CVE-2024-27980 mitigation
(``IsWindowsBatchFile`` in ``src/spawn_sync.cc``): the spawn answers EINVAL
unless ``shell: true``. ``shell: true`` is not the way out — it hands the argv to
``cmd.exe`` to re-parse, and these arguments are filenames straight out of the
checked-out branch (``test_a_filename_can_never_execute_a_command``). Spawning
the bare name is no better: ``CreateProcess`` appends only ``.exe``, so the shim
is never reached and an installed tool answers "command not found".

So the shim is never involved: the package's own ``bin`` names a JavaScript file
and the node already running spawns it. That is one answer on both platforms, so
nothing here pins one — what these cases assert is true of the Mac they were
written on and of the Windows runner alike, which is what CLAUDE.md prefers to
pinning.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import NamedTuple

import pytest
from node_tool_stub import entry_script, install, spawns

SENSORS = Path(__file__).parents[1] / "src" / "habit_hooks_typescript" / "sensors"

BIN_SHIM = "node_modules/.bin"


class WrappedTool(NamedTuple):
    """One sensor and the third-party tool it spawns, set up to run once."""

    sensor: str
    tool: str
    report: str
    argv: tuple[str, ...]


KNIP = WrappedTool("knip.cjs", "knip", json.dumps({"files": [], "issues": []}), ())
ESLINT = WrappedTool("eslint.cjs", "eslint", json.dumps([]), ("--", "src/a.ts"))

wrapped_tool = pytest.mark.parametrize(
    "wrapped", [KNIP, ESLINT], ids=[KNIP.tool, ESLINT.tool]
)


def _spawned(tmp_path: Path, wrapped: WrappedTool) -> tuple[Path, list[list[str]]]:
    """Every whole argv the sensor spawned its tool with, and the project it ran
    in. Every one of them, because knip runs a gated second pass and a rule about
    how a tool is spawned holds for each time it is."""
    project = tmp_path / "demo"
    project.mkdir()
    (project / "package.json").write_text('{"name": "demo"}', encoding="utf-8")
    install(project, wrapped.tool, wrapped.report)
    subprocess.run(
        ["node", str(SENSORS / wrapped.sensor), *wrapped.argv],
        cwd=project,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    spawns_of = spawns(project, wrapped.tool)
    assert spawns_of, "the sensor spawned nothing"
    return project, spawns_of


@wrapped_tool
def test_the_tool_is_spawned_as_the_script_its_package_names(
    wrapped: WrappedTool, tmp_path: Path
) -> None:
    """The file `node_modules/.bin/<tool>` would have run, run directly."""
    project, spawned = _spawned(tmp_path, wrapped)

    named = str(entry_script(project, wrapped.tool))
    assert [run[1] for run in spawned] == [named] * len(spawned)


@wrapped_tool
def test_nothing_from_the_bin_directory_is_spawned(
    wrapped: WrappedTool, tmp_path: Path
) -> None:
    """The shim is the thing that cannot be spawned, so nothing may name it."""
    _, spawned = _spawned(tmp_path, wrapped)

    assert [word for run in spawned for word in run if BIN_SHIM in word] == []


@wrapped_tool
def test_the_interpreter_is_named_by_its_own_file(
    wrapped: WrappedTool, tmp_path: Path
) -> None:
    """A script needs an interpreter named, and it has to be a file — a bare
    `node` would be looked up again, by the very rule that loses a `.cmd`."""
    _, spawned = _spawned(tmp_path, wrapped)

    assert [run[0] for run in spawned if not Path(run[0]).is_file()] == []

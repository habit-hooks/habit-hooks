"""Asking ``sensors/project_tool.cjs`` what it makes of a tool's run.

The seam is a CommonJS module with no CLI of its own, so a case reaches it
through a driver script that requires it, hands it one run and prints its two
answers — whether the run broke, and the complaint it earned.

The driver takes the run either way round. Given only a tool name it really
spawns one, which is how a stub's exit code, signal and output become the
seam's input. Given a run *described* to it as JSON it spawns nothing: with no
ceiling on what a tool may print, a spawn that never completed cannot be
provoked through this seam any more, and describing one is the only way left to
reach the branches that answer for it — quicker, too, than arranging a real
failure for a question that is only about the words.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from node_tool_stub import install_script

SEAM = (
    Path(__file__).parents[1]
    / "src"
    / "habit_hooks_typescript"
    / "sensors"
    / "project_tool.cjs"
)

# The paths arrive as arguments so this stays a constant with nothing spliced
# into it: a JavaScript object literal and Python's own formatting do not mix.
DRIVER = """const [seam, tool, described] = process.argv.slice(2);
const projectTool = require(seam);
const result =
  described === undefined ? projectTool.run(tool, []) : JSON.parse(described);
process.stdout.write(
  JSON.stringify({
    broke: projectTool.broke(result),
    complaint: projectTool.complaint(tool, result),
    printed: (result.stdout || "").length,
    status: result.status ?? null,
    signal: result.signal ?? null,
  }),
);
"""


def run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def a_project_whose_tool(tmp_path: Path, tool: str, cli: str) -> Path:
    """A project holding one installed tool, whose CLI is ``cli``."""
    project = tmp_path / tool
    project.mkdir()
    (project / "package.json").write_text('{"name": "demo"}', encoding="utf-8")
    install_script(project, tool, cli)
    return project


def _driver(directory: Path) -> Path:
    driver = directory / "seam-driver.cjs"
    driver.write_text(DRIVER, encoding="utf-8")
    return driver


def _answer(argv: list[str], cwd: Path) -> dict:
    result = run(["node", *argv], cwd)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def ask_the_seam(project: Path, tool: str) -> dict:
    """What the seam makes of really running ``tool`` in ``project``."""
    return _answer([str(_driver(project.parent)), str(SEAM), tool], project)


def judge(tmp_path: Path, tool: str, described: dict) -> dict:
    """What the seam makes of a run described to it, with nothing spawned."""
    return _answer(
        [str(_driver(tmp_path)), str(SEAM), tool, json.dumps(described)], tmp_path
    )

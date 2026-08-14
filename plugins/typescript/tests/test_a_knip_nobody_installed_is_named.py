"""The tool this sensor spawns must answer in one line when nobody installed it.

``knip.cjs`` shells out to ``knip`` the way the php and python plugins shell out
to their own tools, and an absent command is a ``spawnSync`` ``ENOENT`` there
just as it is a ``FileNotFoundError`` in Python. Reported raw it reached the
runner as ``Error: spawnSync knip ENOENT``, which the phrase the runner looks for
(``part_output.COMMAND_NOT_FOUND``) cannot match — so the one failure with an
obvious fix was the one that did not get told how to fix it, while `jscpd`,
`deptry` and `php` all did (#114).

``node`` itself is on PATH here: the missing tool is knip, not the runtime, and
the two answer differently.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

SENSOR = (
    Path(__file__).resolve().parents[1]
    / "src/habit_hooks_typescript/sensors/knip.cjs"
)


def _path_with_node_but_no_knip(tmp_path: Path) -> str:
    """A PATH carrying the node binary and nothing else the sensor could find."""
    node = shutil.which("node")
    assert node is not None, "this suite needs node"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "node").symlink_to(node)
    return str(bin_dir)


def test_a_knip_nobody_installed_answers_the_way_a_shell_does(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    (project / "package.json").write_text('{ "name": "demo" }', encoding="utf-8")

    result = subprocess.run(
        ["node", str(SENSOR)],
        cwd=project,
        capture_output=True,
        text=True,
        env={**os.environ, "PATH": _path_with_node_but_no_knip(tmp_path)},
        check=False,
    )

    assert result.returncode != 0
    assert result.stdout.strip() == ""
    assert result.stderr.strip() == "knip: command not found"

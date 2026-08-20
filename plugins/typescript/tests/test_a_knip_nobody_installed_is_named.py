"""The tool this sensor spawns must answer in one line when nobody installed it.

``knip.cjs`` runs knip the way the php and python plugins run their own tools,
and an absent tool has to say so in the phrase the runner looks for
(``part_output.COMMAND_NOT_FOUND``) — otherwise the one failure with an obvious
fix is the one that does not get told how to fix it, while `jscpd`, `deptry` and
`php` all do (#114). Reported raw it used to reach the runner as
``Error: spawnSync knip ENOENT``, which that phrase cannot match; now knip is
looked for as the project's own package, so absence is a package that is not
there rather than a name PATH could not resolve — and it is
``sensors/project_tool.cjs`` that turns it back into the shell's own words.

``node`` itself is present here: the missing tool is knip, not the runtime, and
the two answer differently.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

SENSOR = (
    Path(__file__).resolve().parents[1]
    / "src/habit_hooks_typescript/sensors/knip.cjs"
)


def test_a_knip_nobody_installed_answers_the_way_a_shell_does(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    (project / "package.json").write_text('{ "name": "demo" }', encoding="utf-8")

    result = subprocess.run(
        ["node", str(SENSOR)],
        cwd=project,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert result.returncode != 0
    assert result.stdout.strip() == ""
    assert result.stderr.strip() == "knip: command not found"

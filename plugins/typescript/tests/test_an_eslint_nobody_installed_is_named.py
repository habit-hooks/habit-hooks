"""The tool this sensor spawns must answer in one line when nobody installed it.

The same first-contact rule the knip sensor answers to (#114): a tool nobody
installed is the one failure with an obvious fix, so it has to arrive in the
phrase the runner coaches on (``part_output.COMMAND_NOT_FOUND``) rather than as a
module-resolution error nothing recognises. Under the old shell recipe `bash`
said this; there is no shell now, so ``sensors/project_tool.cjs`` says it.

``node`` itself is present here: the missing tool is eslint, not the runtime.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

SENSOR = (
    Path(__file__).resolve().parents[1]
    / "src/habit_hooks_typescript/sensors/eslint.cjs"
)


def _run(project: Path, *argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["node", str(SENSOR), *argv],
        cwd=project,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "demo"
    (project / "src").mkdir(parents=True)
    (project / "package.json").write_text('{ "name": "demo" }', encoding="utf-8")
    (project / "src" / "a.ts").write_text("export const a = 1;\n", encoding="utf-8")
    return project


def test_an_eslint_nobody_installed_answers_the_way_a_shell_does(
    tmp_path: Path,
) -> None:
    result = _run(_project(tmp_path), "--", "src/a.ts")

    assert result.returncode != 0
    assert result.stdout.strip() == ""
    assert result.stderr.strip() == "eslint: command not found"


def test_a_scope_with_nothing_to_lint_never_reaches_for_eslint(tmp_path: Path) -> None:
    """A scope that narrows to nothing eslint lints is a clean empty run, not a
    missing tool: the run has to be able to say "nothing here" without needing
    the tool installed to say it."""
    result = _run(_project(tmp_path), "--", "README.md")

    assert result.returncode == 0
    assert result.stdout == "[]"
    assert result.stderr == ""

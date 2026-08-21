"""However much a tool prints, all of it reaches the sensor that ran it.

Node's ``spawnSync`` caps each captured stream at 1 MB unless told otherwise,
and answers ENOBUFS above it: a truncated stdout, a ``null`` status and an
``error`` the caller has to notice. A real project crosses that cap easily —
forty files of ordinary lint findings do — and the sensor is then left with
nothing it can parse, so a repository full of smells arrives as a broken sensor
instead of as coaching (#142).

The cap is the seam's question, not either caller's: knip capped its own run
generously and eslint never capped its own at all, which is the divergence that
let the bug ship in one of them. So both are asked here, and the answer they
share comes from ``sensors/project_tool.cjs``. Every other suite in this
directory drives a report comfortably under the cap, which is the other side of
that boundary.

eslint is driven for real, because the report that broke #142 was one eslint
wrote. knip is driven by the recording stub, since what knip would make of a
huge tree is not the question — how much of what it printed comes back is.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import eslint_project
from node_tool_stub import install

# What `spawnSync` allows per stream when nobody says otherwise.
NODE_DEFAULT_MAX_BUFFER = 1024 * 1024

SENSORS = Path(__file__).parents[1] / "src" / "habit_hooks_typescript" / "sensors"

# Each line earns two messages from the shipped config — `no-var` and `eqeqeq` —
# and eslint reports every one with the file's absolute path, so the fixture is
# sized to clear the cap by a third rather than to sit on it: where the fixture
# lives moves the byte count.
SMELLY_LINES_PER_FILE = 60
SMELLY_FILES = 40

# Enough unused files for knip's report to cross the cap by the same margin.
DEAD_FILE_COUNT = 30_000
DEAD_FILE = "src/generated/never-imported/module-{number:05d}.ts"


def _smelly_file() -> str:
    return "".join(
        f"var x{n} = 1; if (x{n} == '1') {{}}\n" for n in range(SMELLY_LINES_PER_FILE)
    )


def _a_project_lint_has_a_lot_to_say_about(tmp_path: Path) -> tuple[Path, list[str]]:
    project = eslint_project.project(tmp_path)
    source = _smelly_file()
    files = []
    for number in range(SMELLY_FILES):
        name = f"src/smelly{number}.ts"
        (project / name).write_text(source, encoding="utf-8")
        files.append(name)
    return project, files


def _messages_in(report: str) -> int:
    return sum(len(file["messages"]) for file in json.loads(report))


def _issues_in(findings: str) -> int:
    return sum(len(finding["issues"]) for finding in json.loads(findings))


def test_the_eslint_sensor_coaches_a_report_over_a_megabyte(tmp_path: Path) -> None:
    project, files = _a_project_lint_has_a_lot_to_say_about(tmp_path)
    report = eslint_project.report(project, tuple(files))
    assert len(report) > NODE_DEFAULT_MAX_BUFFER, "fixture no longer crosses the cap"

    result = eslint_project.sensor_run(project, tuple(files))

    assert result.returncode == 0, result.stderr
    assert _issues_in(result.stdout) == _messages_in(report)


def _a_knip_with_a_lot_to_report(tmp_path: Path) -> tuple[Path, str]:
    project = tmp_path / "demo"
    project.mkdir()
    (project / "package.json").write_text('{"name": "demo"}', encoding="utf-8")
    report = json.dumps(
        {
            "files": [
                DEAD_FILE.format(number=number) for number in range(DEAD_FILE_COUNT)
            ],
            "issues": [],
        }
    )
    install(project, "knip", report)
    return project, report


def test_the_knip_sensor_coaches_a_report_over_a_megabyte(tmp_path: Path) -> None:
    project, report = _a_knip_with_a_lot_to_report(tmp_path)
    assert len(report) > NODE_DEFAULT_MAX_BUFFER, "fixture no longer crosses the cap"

    result = subprocess.run(
        ["node", str(SENSORS / "knip.cjs")],
        cwd=project,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert _issues_in(result.stdout) == DEAD_FILE_COUNT

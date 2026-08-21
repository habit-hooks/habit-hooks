"""A smell about the whole file arrives from eslint with no position (#140).

``max-lines`` reports at the first line past the limit, and ``oversized-file``
is not about that line — the generic ``line-count`` sensor reports the same
smell about the same file and names no line at all. Carrying eslint's is what
stopped the two being recognised as one observation, so the reader was coached
twice about one file.

eslint is stubbed by ``node_tool_stub``, as in
``test_the_eslint_sensor_shapes_its_findings.py``: the canned report is eslint's
own JSON shape, so what is under test is the transform and nothing else.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from node_tool_stub import install

SENSOR = Path(__file__).parents[1] / "src/habit_hooks_typescript/sensors/eslint.cjs"

ESLINT = "eslint"


def _report(rule: str | None, **extra: object) -> str:
    """One message about ``src/a.ts``, positioned where eslint positions one."""
    message = {
        "ruleId": rule,
        "message": "something to fix",
        "severity": 2,
        "line": 201,
        "column": 1,
        **extra,
    }
    return json.dumps([{"filePath": "/p/src/a.ts", "messages": [message]}])


def _details(tmp_path: Path, report: str) -> dict:
    project = tmp_path / "demo"
    project.mkdir()
    (project / "package.json").write_text('{"name": "demo"}', encoding="utf-8")
    install(project, ESLINT, report)
    result = subprocess.run(
        ["node", str(SENSOR), "--", "src/a.ts"],
        cwd=project,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return json.loads(result.stdout)[0]["issues"][0]["details"]


def test_an_oversized_file_names_no_line_and_no_column(tmp_path: Path) -> None:
    """Line 201 is where eslint's counter tripped, not where the problem is."""
    details = _details(tmp_path, _report("max-lines"))

    assert details["line"] is None
    assert details["column"] is None


def test_an_oversized_file_still_carries_the_message_eslint_wrote(
    tmp_path: Path,
) -> None:
    """Only the position goes: eslint's own words say how far over the file is,
    and nothing else reports that."""
    details = _details(tmp_path, _report("max-lines"))

    assert details["message"] == "something to fix"
    assert details["source"] == "eslint:max-lines"


def test_a_line_level_smell_keeps_the_position_it_was_given(tmp_path: Path) -> None:
    """Every other smell this sensor emits is about a line, and the line is the
    only thing telling two of them in one file apart."""
    details = _details(tmp_path, _report("eqeqeq"))

    assert details["line"] == 201
    assert details["column"] == 1


def test_a_parse_error_keeps_where_parsing_failed(tmp_path: Path) -> None:
    """``parse-error`` is file-level too — its guide lists files, not lines —
    but eslint's position on it is where the syntax actually broke, and no other
    sensor reports it for the same file, so there is nothing to reconcile and
    real information to lose."""
    details = _details(tmp_path, _report(None, fatal=True))

    assert details["line"] == 201

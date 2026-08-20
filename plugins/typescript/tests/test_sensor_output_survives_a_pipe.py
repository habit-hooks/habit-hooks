"""The JS sensors must deliver complete JSON when stdout is a pipe.

Node's writes to a pipe are asynchronous, so a sensor that calls
``process.exit()`` straight after ``process.stdout.write`` is killed before the
write drains and its output is cut at the pipe buffer (~64KB). The runner always
captures sensor output through a pipe (``execution._run``), so any payload past
that boundary arrives as invalid JSON. Redirecting to a file hides the bug —
file writes are synchronous — hence the pipe here, and a fixture big enough to
cross the boundary.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

PIPE_BUFFER_BYTES = 64 * 1024
PLUGIN = Path(__file__).parents[1]
SENSORS = PLUGIN / "src" / "habit_hooks_typescript" / "sensors"

# Each comment yields ~200 bytes of JSON, so this clears the buffer several times
# over — a fixture that stays under it passes whether or not the bug is present.
COMMENT_COUNT = 1500


def _source_with_many_comments(tmp_path: Path) -> Path:
    source = tmp_path / "many-comments.ts"
    lines = [
        f"// a non-essential comment number {n}\nconst v{n} = {n};"
        for n in range(COMMENT_COUNT)
    ]
    source.write_text("\n".join(lines), encoding="utf-8")
    return source


def test_comment_sensor_emits_complete_json_through_a_pipe(tmp_path: Path) -> None:
    source = _source_with_many_comments(tmp_path)

    result = subprocess.run(
        ["node", str(SENSORS / "comment.cjs"), str(source)],
        # The helper resolves ts-morph from the directory it is run in, as it
        # does in a consumer project, so the run needs one that has it.
        cwd=PLUGIN,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    findings = json.loads(result.stdout)
    assert findings[0]["smell"] == "non-essential-comment"
    assert len(findings[0]["issues"]) == COMMENT_COUNT
    assert len(result.stdout) > PIPE_BUFFER_BYTES, "fixture no longer crosses the buffer"

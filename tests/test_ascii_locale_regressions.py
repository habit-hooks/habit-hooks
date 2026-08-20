"""Reproduces issue #133 outside this Mac's usual locale.

``locale.getencoding()`` cannot be monkeypatched in-process -- CPython decides
it once, at interpreter start -- so these run the real ``habit-mapper`` entry
point in a subprocess whose environment forces the same non-UTF-8 locale CI
hit on Windows: ``PYTHONUTF8=0 PYTHONCOERCECLOCALE=0 LC_ALL=C``. That
combination reproduces byte-for-byte on this Mac too (see the project
CLAUDE.md's #133 note), which is what makes it a fair stand-in for Windows'
cp1252 default without a Windows machine to run on.

Two directions, because the bug had two: a guide decoded off disk, and this
tool's own output encoded back onto the console. The read side crashed first
and hid the write side from the original report entirely.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from plugin_fixture import write_plugin, write_project_config

ASCII_LOCALE_ENV = {
    **os.environ,
    "PYTHONUTF8": "0",
    "PYTHONCOERCECLOCALE": "0",
    "LC_ALL": "C",
}

# Run the real entry point, not a call into habit_hooks.mapper: run_console()
# is where the write-side fix lives, so calling anything closer to the metal
# would test around it rather than through it.
_RUN_MAPPER = "import sys; from habit_hooks.mapper import main; sys.exit(main([]))"

_ISSUE = {"key": "src/a.py", "details": {"file": "src/a.py"}}


def _finding_for(smell: str) -> dict:
    return {"smell": smell, "details": {}, "issues": [_ISSUE]}


def _run_mapper_under_ascii_locale(
    project_dir: Path, findings: list[dict]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", _RUN_MAPPER],
        cwd=project_dir,
        env=ASCII_LOCALE_ENV,
        input=json.dumps(findings),
        capture_output=True,
        # No errors="replace" here, unlike sensors.spawn's usual policy: strict
        # decoding of the mapper's own output is the point of this test.
        encoding="utf-8",
    )


def test_a_guide_containing_non_ascii_text_is_read_correctly(tmp_path: Path) -> None:
    """A UTF-8 guide decoded under a non-UTF-8 locale used to raise
    ``UnicodeDecodeError`` out of ``guide.read_text()`` before a single byte of
    it reached stdout (#133) -- so this fails before the write side is ever
    reached, whatever the write side does.
    """
    write_plugin(
        tmp_path,
        "fixt",
        {"guides/oversized-file.md": "Split the file — the seams are usually clear.\n"},
    )
    write_project_config(tmp_path, 'plugins = ["fixt"]')

    result = _run_mapper_under_ascii_locale(tmp_path, [_finding_for("oversized-file")])

    assert "Split the file — the seams are usually clear." in result.stdout


def test_non_ascii_output_reaches_stdout_correctly(tmp_path: Path) -> None:
    """Every rendered finding is prefixed with a banner this project writes
    itself -- box-drawing characters, whatever the guide says -- so printing
    even a plain-ASCII guide used to raise ``UnicodeEncodeError`` on a non-
    UTF-8 console. The guide here carries no non-ASCII text at all, which is
    what isolates this from the read-side case above: decoding it succeeds
    whether or not a call site names its encoding.
    """
    write_plugin(
        tmp_path,
        "fixt",
        {"guides/oversized-file.md": "Split the file into smaller pieces.\n"},
    )
    write_project_config(tmp_path, 'plugins = ["fixt"]')

    result = _run_mapper_under_ascii_locale(tmp_path, [_finding_for("oversized-file")])

    assert "── oversized-file (1 issue) ──" in result.stdout

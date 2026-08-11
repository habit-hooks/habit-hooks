"""Running the knip sensor over a project whose `knip` is a recording stub.

The stub prints an empty run and appends the argv it was spawned with to a log,
so a suite can ask what the sensor *did* — which config it named, how many passes
it ran — rather than what knip made of it. The real tool is exercised by
``plugins/typescript/docs/typescript-plugin.spec.md``.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path

PLUGIN = Path(__file__).parents[1]
PACKAGE = PLUGIN / "src" / "habit_hooks_typescript"
SENSOR = PACKAGE / "sensors" / "knip.cjs"
SHIPPED_CONFIG = PACKAGE / "knip.json"

EMPTY_REPORT = {"files": [], "issues": []}

RECORDING_STUB = """#!/bin/sh
printf '%s\\t' "$@" >> "$(dirname "$0")/argv.log"
printf '\\n' >> "$(dirname "$0")/argv.log"
cat "$(dirname "$0")/report.json"
"""


def project(tmp_path: Path) -> Path:
    """A project whose `knip` on PATH records its argv and prints an empty run."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "report.json").write_text(json.dumps(EMPTY_REPORT), encoding="utf-8")
    stub = bin_dir / "knip"
    stub.write_text(RECORDING_STUB, encoding="utf-8")
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)

    created = tmp_path / "demo"
    created.mkdir()
    (created / "package.json").write_text('{"name": "demo"}', encoding="utf-8")
    return created


def passes(project: Path, args: tuple[str, ...] = ()) -> list[list[str]]:
    """The argv of every knip the sensor spawned, in order.

    ``args`` is what the runner splices into ``${args}`` from the project's
    ``[sensors.knip] args``, arriving as the sensor helper's own argv.
    """
    bin_dir = project.parent / "bin"
    subprocess.run(
        ["node", str(SENSOR), *args],
        cwd=project,
        env={**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"},
        capture_output=True,
        text=True,
        check=True,
    )
    log = (bin_dir / "argv.log").read_text(encoding="utf-8")
    return [line.rstrip("\t").split("\t") for line in log.splitlines()]

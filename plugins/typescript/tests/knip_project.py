"""Running the knip sensor over a project whose `knip` is a recording stub.

The stub (``node_tool_stub``) prints an empty run and records the argv it was
spawned with, so a suite can ask what the sensor *did* — which config it named,
how many passes it ran — rather than what knip made of it. The real tool is
exercised by ``plugins/typescript/docs/typescript-plugin.spec.md``.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from node_tool_stub import install, spawns

PLUGIN = Path(__file__).parents[1]
PACKAGE = PLUGIN / "src" / "habit_hooks_typescript"
SENSOR = PACKAGE / "sensors" / "knip.cjs"
SHIPPED_CONFIG = PACKAGE / "knip.json"

KNIP = "knip"
EMPTY_REPORT = {"files": [], "issues": []}


def project(tmp_path: Path) -> Path:
    """A project whose `knip` records its argv and prints an empty run."""
    created = tmp_path / "demo"
    created.mkdir()
    (created / "package.json").write_text('{"name": "demo"}', encoding="utf-8")
    install(created, KNIP, json.dumps(EMPTY_REPORT))
    return created


def passes(project: Path, args: tuple[str, ...] = ()) -> list[list[str]]:
    """The arguments of every knip the sensor spawned, in order.

    ``args`` is what the runner splices into ``${args}`` from the project's
    ``[sensors.knip] args``, arriving as the sensor helper's own argv. The first
    two entries of each spawn are the node running it and knip's own script —
    that the shim was bypassed is
    ``test_a_wrapped_tool_never_needs_its_shim.py``'s subject, not this one's.
    """
    subprocess.run(
        ["node", str(SENSOR), *args],
        cwd=project,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return [spawn[2:] for spawn in spawns(project, KNIP)]

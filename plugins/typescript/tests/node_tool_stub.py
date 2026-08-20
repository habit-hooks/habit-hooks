"""A stand-in for one of the project's Node CLIs, installed where the real one goes.

The stub prints a canned report and appends the argv it was spawned with to a
log, so a suite can ask what the sensor *did* — which config it named, how many
passes it ran, what it spawned the tool as — rather than what the real tool made
of it. The real tools are exercised by ``docs/typescript-plugin.spec.md``.

It is installed as a **package** rather than dropped on ``PATH`` because that is
where the sensors now look: a CLI is spawned as the JavaScript file its
``package.json`` ``bin`` names, never as the shim ``node_modules/.bin`` holds
(``sensors/project_tool.cjs``). A ``PATH`` stub would answer a question nothing
asks any more — and, being a shell script, would not have answered it on Windows
at all.
"""

from __future__ import annotations

import json
from pathlib import Path

ARGV_LOG = "argv.log"
REPORT = "report.json"

# Full `process.argv`, so a case can ask what ran the tool as well as what the
# tool was asked — argv[0] is the node that spawned it and argv[1] its own file.
RECORDER = """const fs = require("node:fs");
const path = require("node:path");
const installed = path.join(__dirname, "..");
fs.appendFileSync(
  path.join(installed, "{log}"),
  `${{process.argv.join("\\t")}}\\n`,
);
process.stdout.write(fs.readFileSync(path.join(installed, "{report}"), "utf8"));
"""


def install(project: Path, tool: str, prints: str) -> Path:
    """``tool`` installed in ``project``, printing ``prints`` whatever it is asked."""
    package = project / "node_modules" / tool
    (package / "bin").mkdir(parents=True)
    (package / "package.json").write_text(
        json.dumps({"name": tool, "version": "0.0.0", "bin": {tool: f"bin/{tool}.js"}}),
        encoding="utf-8",
    )
    (package / REPORT).write_text(prints, encoding="utf-8")
    (package / "bin" / f"{tool}.js").write_text(
        RECORDER.format(log=ARGV_LOG, report=REPORT), encoding="utf-8"
    )
    return package


def entry_script(project: Path, tool: str) -> Path:
    """The file ``node_modules/.bin/<tool>`` would have run."""
    return project / "node_modules" / tool / "bin" / f"{tool}.js"


def spawns(project: Path, tool: str) -> list[list[str]]:
    """Every spawn of ``tool``, whole, in order."""
    log = project / "node_modules" / tool / ARGV_LOG
    if not log.is_file():
        return []
    return [line.split("\t") for line in log.read_text(encoding="utf-8").splitlines()]

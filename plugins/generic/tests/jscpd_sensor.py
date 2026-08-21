"""Running the shipped jscpd sensor against a throwaway project.

Shared by the suites that drive the real tool: what the sensor *decides* (whose
config is in play), what it *concludes* (a run that failed is not a clean one),
and which jscpd it spawns. They all need the same spawn, and the ``jscpd``
fixture in ``conftest.py`` answers for the tool itself.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SENSOR = (
    Path(__file__).resolve().parents[1]
    / "src/habit_hooks_generic/sensors/jscpd.py"
)

CLONED_BLOCK = (
    "export function {name}(x: number, y: number) {{\n"
    "  const sum = x + y;\n"
    "  const product = x * y;\n"
    "  const diff = x - y;\n"
    "  const quotient = x / y;\n"
    "  const scaled = sum * product;\n"
    "  const shifted = diff - quotient;\n"
    "  const blended = scaled + shifted;\n"
    "  return {{ sum, product, diff, quotient, scaled, shifted, blended }};\n"
    "}}\n"
)


# jscpd 4 resolves a config's `path` entries against the config file's directory
# (`readConfigJson`), which makes them absolute, and @jscpd/finder then hands
# `<resolved>/**/*` to fast-glob. On Windows that resolution spells the
# separators `\`, which fast-glob reads as escape characters rather than
# separators — so the glob matches nothing and jscpd scans zero files, exits 0
# and writes no report. It is the tool's own blindness, not the sensor's: bare
# `jscpd` in such a project answers the same, and with no `path` anywhere jscpd
# scans `process.cwd()`, absolute again. A positional path stays relative and is
# unaffected, which is why the cases where the plugin's own config is in play
# still run there. Whose config won is therefore unobservable on Windows: the
# only run that can show it is one that scans something.
A_JSCPD_THAT_CAN_SCAN_FROM_A_CONFIG = pytest.mark.skipif(
    os.name == "nt",
    reason="jscpd resolves a config's path to an absolute one, which on Windows "
    "is a glob matching no file at all",
)


def run_sensor(
    project: Path, jscpd: str, arguments: list[str]
) -> subprocess.CompletedProcess[str]:
    """The sensor's own run, from ``project``, handed ``jscpd`` to spawn.

    The sensor names its tool (``${detector:jscpd}``) and a run resolves that to
    a file before spawning it, so the file arrives first among its arguments.
    This stands in for the run, and hands it over the same way.
    """
    return subprocess.run(
        [sys.executable, str(SENSOR), jscpd, *arguments],
        cwd=project,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )


def write_json(path: Path, content: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content), encoding="utf-8")
    return path


def write_clones(directory: Path, names: list[str]) -> None:
    """One file per name, each holding the same block, so jscpd sees clones."""
    directory.mkdir(parents=True, exist_ok=True)
    for name in names:
        (directory / f"{name}.ts").write_text(CLONED_BLOCK.format(name=name), encoding="utf-8")

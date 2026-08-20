"""Running the shipped jscpd sensor against a throwaway project.

Shared by the two suites that drive the real tool: what the sensor *decides*
(whose config is in play) and what it *concludes* (a run that failed is not a
clean one). Both need jscpd on PATH, so both need the same skip and the same
spawn, and neither is a spec case — a spec case runs in a temp project where
jscpd is not installed.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
SENSOR = _REPO_ROOT / "plugins/generic/src/habit_hooks_generic/sensors/jscpd.py"
JSCPD_BIN = _REPO_ROOT / "node_modules" / ".bin"

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


def requires_jscpd() -> None:
    if not (JSCPD_BIN / "jscpd").exists():
        pytest.skip("jscpd is not installed at the repo root (pnpm install)")


def run_sensor(
    project: Path, arguments: list[str], path: str | None = None
) -> subprocess.CompletedProcess[str]:
    """The sensor's own run, from ``project``, with the real jscpd on PATH.

    ``path`` replaces that PATH outright, which is how the missing-tool case
    proves what the sensor says when jscpd is nowhere to be found (#114).
    """
    environment = dict(os.environ)
    environment["PATH"] = (
        path if path is not None else f"{JSCPD_BIN}{os.pathsep}{environment['PATH']}"
    )
    return subprocess.run(
        [sys.executable, str(SENSOR), *arguments],
        cwd=project,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
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

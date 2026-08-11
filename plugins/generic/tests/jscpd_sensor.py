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
        text=True,
        env=environment,
    )


def write_json(path: Path, content: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content))
    return path


def write_clones(directory: Path, names: list[str]) -> None:
    """One file per name, each holding the same block, so jscpd sees clones."""
    directory.mkdir(parents=True, exist_ok=True)
    for name in names:
        (directory / f"{name}.ts").write_text(CLONED_BLOCK.format(name=name))

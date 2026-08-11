"""Running the real eslint over a throwaway consumer project.

Shared by the three suites that drive it: what the **shipped config** reports,
what the sensor's **smell map** makes of a rule ID, and **which config wins**.
All three need the plugin's own ``node_modules`` on PATH and a project laid out
the way a consumer's is, and none is a spec case — a spec case runs in a temp
project with no tools in it.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import tomllib
from pathlib import Path

PLUGIN = Path(__file__).parents[1]
PACKAGE = PLUGIN / "src" / "habit_hooks_typescript"
SENSORS = PACKAGE / "sensors"
SHIPPED_CONFIG = PACKAGE / "eslint.config.mjs"

MANIFEST = '{ "name": "demo", "version": "0.0.0" }\n'

# An interface declaring two method signatures, and one genuinely unused local.
# The parameter names are the false positives; ``unusedTax`` is the real find.
REPOSITORY_TS = """export interface Repository {
  save(item: string): void;
  find(id: string): string;
}

export function total(prices: number[]): number {
  const unusedTax = 0.2;
  return prices.length;
}
"""
UNUSED_LOCAL_LINE = 7


def project(tmp_path: Path) -> Path:
    """A consumer project with the plugin's Node tools and one TypeScript file."""
    created = tmp_path / "demo"
    (created / "src").mkdir(parents=True)
    (created / "package.json").write_text(MANIFEST, encoding="utf-8")
    (created / "node_modules").symlink_to(PLUGIN / "node_modules")
    (created / "src" / "repository.ts").write_text(REPOSITORY_TS, encoding="utf-8")
    return created


def run(project: Path, script: str) -> subprocess.CompletedProcess[str]:
    """``script`` under bash with the project's tool bins on PATH, as the runner
    spawns a sensor (``sensors/spawn.py``)."""
    path = f"{project / 'node_modules' / '.bin'}{os.pathsep}{os.environ['PATH']}"
    return subprocess.run(
        ["bash", "-c", script],
        cwd=project,
        env={**os.environ, "PATH": path},
        capture_output=True,
        text=True,
        check=False,
    )


def messages(project: Path, config: Path) -> list[dict]:
    """What eslint says about the project's one file under ``config``."""
    script = (
        f"eslint -f json --no-warn-ignored --config {shlex.quote(str(config))} "
        "src/repository.ts"
    )
    result = run(project, script)
    assert result.stdout, result.stderr
    return json.loads(result.stdout)[0]["messages"]


def sensor_run(
    project: Path,
    files: tuple[str, ...] = ("src/repository.ts",),
    args: tuple[str, ...] = (),
) -> subprocess.CompletedProcess[str]:
    """What the eslint sensor's command does over ``files``, as the runner does it.

    The placeholders are filled the way the runner fills them
    (``sensors/command_text.py``): ``${dir}`` is the sensor directory, ``${files}``
    the scoped paths and ``${args}`` the project's ``[sensors.eslint] args``, each
    already shell-quoted.
    """
    command = tomllib.loads(SENSORS.joinpath("eslint.toml").read_text("utf-8"))
    script = (
        command["command"]
        .replace("${dir}", shlex.quote(str(SENSORS)))
        .replace("${args}", _quoted(args))
        .replace("${files}", _quoted(files))
    )
    return run(project, script)


def _quoted(values: tuple[str, ...]) -> str:
    return " ".join(shlex.quote(value) for value in values)


def sensor_findings(
    project: Path,
    files: tuple[str, ...] = ("src/repository.ts",),
    args: tuple[str, ...] = (),
) -> list[dict]:
    """The eslint sensor's findings for ``files``, defaulting to the fixture's one."""
    result = sensor_run(project, files, args)
    assert result.stdout, result.stderr
    return json.loads(result.stdout)

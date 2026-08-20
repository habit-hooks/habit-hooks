"""Running the real eslint over a throwaway consumer project.

Shared by the three suites that drive it: what the **shipped config** reports,
what the sensor's **smell map** makes of a rule ID, and **which config wins**.
All three need the plugin's own ``node_modules`` on PATH and a project laid out
the way a consumer's is, and none is a spec case — a spec case runs in a temp
project with no tools in it.

Nothing here spawns a shell, and nothing spawns eslint by name: the sensor runs
it as the JavaScript file its package's ``bin`` names, and so does this. Both are
the same fact — a shell recipe cannot run on native Windows and a ``.cmd`` shim
cannot be spawned there — so a fixture that reached for either would be testing
the sensor on one platform only.
"""

from __future__ import annotations

import json
import os
import subprocess
import tomllib
from pathlib import Path

PLUGIN = Path(__file__).parents[1]
PACKAGE = PLUGIN / "src" / "habit_hooks_typescript"
SENSORS = PACKAGE / "sensors"
SHIPPED_CONFIG = PACKAGE / "eslint.config.mjs"
ESLINT = PLUGIN / "node_modules" / "eslint" / "bin" / "eslint.js"

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


def run(project: Path, argv: list[str]) -> subprocess.CompletedProcess[str]:
    """``argv`` with the project's tool bins on PATH, as the runner spawns a
    sensor (``sensors/spawn.py``)."""
    path = f"{project / 'node_modules' / '.bin'}{os.pathsep}{os.environ['PATH']}"
    return subprocess.run(
        argv,
        cwd=project,
        env={**os.environ, "PATH": path},
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def messages(project: Path, config: Path) -> list[dict]:
    """What eslint says about the project's one file under ``config``."""
    result = run(
        project,
        [
            "node",
            str(ESLINT),
            "-f",
            "json",
            "--no-warn-ignored",
            "--config",
            str(config),
            "src/repository.ts",
        ],
    )
    assert result.stdout, result.stderr
    return json.loads(result.stdout)[0]["messages"]


def sensor_argv(
    files: tuple[str, ...] = ("src/repository.ts",),
    args: tuple[str, ...] = (),
) -> list[str]:
    """The eslint sensor's argv, expanded as the runner expands it.

    ``sensors/command_text.py`` substitutes ``${dir}`` inside the element it
    stands in and replaces an element that is exactly ``${args}`` or ``${files}``
    with the arguments it stands for — quoted not at all, because no shell reads
    an argv.
    """
    spec = tomllib.loads(SENSORS.joinpath("eslint.toml").read_text(encoding="utf-8"))
    lists = {"${args}": list(args), "${files}": list(files)}
    return [
        argument
        for element in spec["argv"]
        for argument in lists.get(element, [element.replace("${dir}", str(SENSORS))])
    ]


def sensor_run(
    project: Path,
    files: tuple[str, ...] = ("src/repository.ts",),
    args: tuple[str, ...] = (),
) -> subprocess.CompletedProcess[str]:
    """What the eslint sensor does over ``files``, as the runner does it."""
    return run(project, sensor_argv(files, args))


def sensor_findings(
    project: Path,
    files: tuple[str, ...] = ("src/repository.ts",),
    args: tuple[str, ...] = (),
) -> list[dict]:
    """The eslint sensor's findings for ``files``, defaulting to the fixture's one."""
    result = sensor_run(project, files, args)
    assert result.stdout, result.stderr
    return json.loads(result.stdout)

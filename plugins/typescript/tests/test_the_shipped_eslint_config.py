"""The config the plugin ships, and the smells the sensor makes of what it says.

The plugin never ran its own flat config, so nothing lined the two up. The
config pairs base ``no-unused-vars`` with ``@typescript-eslint/no-unused-vars``,
and it had them the wrong way round: the base rule cannot see type positions, so
an interface's method parameter names — documentation, and not removable without
breaking the TypeScript — came back as unused variables at error severity. Turn
the pairing the right way round and the reporting moves to the TypeScript rule,
which the sensor's smell map then has to name, or the fix pushes the finding out
of the vocabulary instead of into it (#113).

Both halves run the real eslint from the plugin's own ``node_modules``: a rule
pairing is only true of the tool that reads it, and a smell map is only true of
the messages that tool emits.
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


def _project(tmp_path: Path) -> Path:
    """A consumer project with the plugin's Node tools and one TypeScript file."""
    project = tmp_path / "demo"
    (project / "src").mkdir(parents=True)
    (project / "package.json").write_text(MANIFEST, encoding="utf-8")
    (project / "node_modules").symlink_to(PLUGIN / "node_modules")
    (project / "src" / "repository.ts").write_text(REPOSITORY_TS, encoding="utf-8")
    return project


def _run(project: Path, script: str) -> subprocess.CompletedProcess[str]:
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


def _messages(project: Path, config: Path) -> list[dict]:
    """What eslint says about the project's one file under ``config``."""
    script = (
        f"eslint -f json --no-warn-ignored --config {shlex.quote(str(config))} "
        "src/repository.ts"
    )
    result = _run(project, script)
    assert result.stdout, result.stderr
    return json.loads(result.stdout)[0]["messages"]


def _sensor_findings(project: Path) -> list[dict]:
    """The eslint sensor's findings for the project's one file.

    The command's placeholders are filled the way the runner fills them
    (``sensors/command_text.py``): ``${dir}`` is the sensor directory, ``${files}``
    the scoped paths.
    """
    command = tomllib.loads(SENSORS.joinpath("eslint.toml").read_text("utf-8"))
    script = (
        command["command"]
        .replace("${dir}", shlex.quote(str(SENSORS)))
        .replace("${args}", "")
        .replace("${files}", shlex.quote("src/repository.ts"))
    )
    result = _run(project, script)
    assert result.stdout, result.stderr
    return json.loads(result.stdout)


def test_an_interface_method_parameter_is_not_an_unused_variable(
    tmp_path: Path,
) -> None:
    """`item` and `id` name what the implementer must pass; only `unusedTax` is
    dead."""
    messages = _messages(_project(tmp_path), SHIPPED_CONFIG)

    assert [message["line"] for message in messages] == [UNUSED_LOCAL_LINE], messages


def test_the_unused_local_is_reported_by_the_typescript_rule(tmp_path: Path) -> None:
    """The pairing decides which rule ID the finding will carry downstream."""
    messages = _messages(_project(tmp_path), SHIPPED_CONFIG)

    assert [message["ruleId"] for message in messages] == [
        "@typescript-eslint/no-unused-vars"
    ]


def test_the_config_loads_from_where_it_ships(tmp_path: Path) -> None:
    """Once the sensor names the shipped config, that file is read from wherever
    habit-hooks is installed — for a consumer, a Python ``site-packages`` tree
    with no ``node_modules`` anywhere above it. A bare ``import`` in the config
    resolves against *that* directory and dies with ``ERR_MODULE_NOT_FOUND``, so
    the parser and plugin have to come from the project, which is where eslint
    itself came from.
    """
    project = _project(tmp_path)
    installed = tmp_path / "site-packages" / "habit_hooks_typescript"
    installed.mkdir(parents=True)
    shipped = installed / SHIPPED_CONFIG.name
    shipped.write_bytes(SHIPPED_CONFIG.read_bytes())

    messages = _messages(project, shipped)

    assert [message["line"] for message in messages] == [UNUSED_LOCAL_LINE], messages


def test_a_flat_config_above_the_project_is_still_the_project_s_own(
    tmp_path: Path,
) -> None:
    """eslint discovers a flat config by walking up from where it runs, so a
    monorepo root's config is one the project already has. The sensor has to
    make the same walk: stopping at the project directory would name ours over a
    config eslint would have found, which is the override the rule forbids."""
    project = _project(tmp_path)
    (tmp_path / "eslint.config.mjs").write_text(
        'export default [{ files: ["**/*.ts"], rules: { "no-console": "error" } }];\n',
        encoding="utf-8",
    )
    (project / "src" / "repository.ts").write_text(
        'console.log("shipping this by accident");\n', encoding="utf-8"
    )

    findings = _sensor_findings(project)

    assert [finding["smell"] for finding in findings] == ["no-console"], findings


def test_the_typescript_rule_arrives_as_the_unused_variable_smell(
    tmp_path: Path,
) -> None:
    """A rule the smell map does not name arrives under its raw ID — uncoached,
    and keyed differently from every other unused variable in the vocabulary."""
    project = _project(tmp_path)
    (project / "eslint.config.mjs").write_bytes(SHIPPED_CONFIG.read_bytes())

    findings = _sensor_findings(project)

    assert [finding["smell"] for finding in findings] == ["unused-variable"], findings
    assert findings[0]["issues"][0]["details"]["source"] == (
        "eslint:@typescript-eslint/no-unused-vars"
    )

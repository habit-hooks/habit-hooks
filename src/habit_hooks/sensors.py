"""habit-sensors: the recursive concat-then-transform ETL runner.

A node's output is ``transformers ∘ concat(child sensors)``. The root and each
plugin are the same shape: the root concatenates its plugins (each a node whose
children are its sensors), then runs the root transformers. Every plugin stamps
its declared ``language`` onto its findings.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import tomllib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from .config import Config, load_config
from .resolve import Resolver, package_root
from .scope import Scope, parse_args, resolve_scope

ACCEPTED_EXIT_CODES = (0, 1)


class SensorError(Exception):
    """A sensor that spawn-failed, exited unexpectedly, or emitted bad JSON."""


@dataclass
class Part:
    name: str
    command: str
    directory: Path
    args: list[str] = field(default_factory=list)


@dataclass
class Plugin:
    name: str
    language: str | None
    sensors: list[Part]
    transformers: list[Part]


@dataclass
class Run:
    findings: list[dict] = field(default_factory=list)
    notices: list[str] = field(default_factory=list)

    @property
    def failed(self) -> bool:
        return bool(self.notices)


def _read_toml(path: Path) -> dict:
    with path.open("rb") as f:
        return tomllib.load(f)


def _sensor_args(name: str, spec: dict, config: Config) -> list[str]:
    override = config.sensors.get(name)
    if override is not None and override.args is not None:
        return override.args
    return spec.get("args", [])


def _resolve_part(
    plugins: list[str],
    kind: str,
    name: str,
    project_dir: Path,
    package_dir: Path,
    config: Config,
) -> Part:
    for plugin in plugins:
        path = Resolver(project_dir, package_dir).in_plugin(
            plugin, f"{kind}/{name}.toml"
        )
        if path is not None:
            spec = _read_toml(path)
            args = _sensor_args(name, spec, config) if kind == "sensors" else []
            return Part(name, spec["command"], path.parent, args)
    raise SystemExit(f"habit-sensors: no {kind[:-1]} {name!r} in {plugins}")


def _load_plugin(
    name: str, config: Config, project_dir: Path, package_dir: Path
) -> Plugin:
    path = Resolver(project_dir, package_dir).in_plugin(name, "config.toml")
    spec = _read_toml(path) if path else {}
    sensors = [
        _resolve_part([name], "sensors", sensor, project_dir, package_dir, config)
        for sensor in spec.get("sensors", [])
        if not _disabled(sensor, config)
    ]
    transformers = [
        _resolve_part(
            [name], "transformers", transformer, project_dir, package_dir, config
        )
        for transformer in spec.get("transformers", [])
    ]
    return Plugin(name, spec.get("language"), sensors, transformers)


def _disabled(sensor: str, config: Config) -> bool:
    override = config.sensors.get(sensor)
    return bool(override and override.disabled)


def _expand(command: str, part: Part, scope: Scope) -> str:
    files = " ".join(scope.files)
    args = " ".join(shlex.quote(arg) for arg in part.args)
    return (
        command.replace("${dir}", str(part.directory))
        .replace("${args}", args)
        .replace("${files}", files)
    )


def _path_env(project_dir: Path) -> dict:
    env = dict(os.environ)
    bins = [project_dir / "node_modules" / ".bin", project_dir / ".venv" / "bin"]
    prefix = os.pathsep.join(str(b) for b in bins)
    env["PATH"] = prefix + os.pathsep + env.get("PATH", "")
    return env


def _run_command(
    command: str, project_dir: Path, stdin: str | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-c", command],
        cwd=project_dir,
        env=_path_env(project_dir),
        input=stdin,
        capture_output=True,
        text=True,
    )


def _parse_findings(stdout: str) -> list[dict]:
    text = stdout.strip()
    findings = json.loads(text) if text else []
    if not isinstance(findings, list):
        raise ValueError("output is not a findings array")
    return findings


def run_sensor(sensor: Part, project_dir: Path, scope: Scope) -> list[dict]:
    command = _expand(sensor.command, sensor, scope)
    result = _run_command(command, project_dir)
    if result.returncode not in ACCEPTED_EXIT_CODES:
        raise SensorError(f"sensor {sensor.name!r} failed: {sensor.command}")
    try:
        return _parse_findings(result.stdout)
    except (ValueError, json.JSONDecodeError):
        raise SensorError(
            f"sensor {sensor.name!r} failed: {sensor.command}"
        ) from None


def _safe_sensor(
    sensor: Part, project_dir: Path, scope: Scope
) -> tuple[list[dict], str | None]:
    try:
        return run_sensor(sensor, project_dir, scope), None
    except SensorError as error:
        return [], f"habit-sensors: {error}"


def _run_sensors(sensors: list[Part], project_dir: Path, scope: Scope) -> Run:
    if not sensors:
        return Run()
    with ThreadPoolExecutor(max_workers=len(sensors)) as pool:
        outputs = list(pool.map(lambda s: _safe_sensor(s, project_dir, scope), sensors))
    run = Run()
    for findings, notice in outputs:
        run.findings.extend(findings)
        if notice:
            run.notices.append(notice)
    return run


def _apply_transformers(
    transformers: list[Part], findings: list[dict], project_dir: Path, scope: Scope
) -> list[dict]:
    for transformer in transformers:
        command = _expand(transformer.command, transformer, scope)
        result = _run_command(command, project_dir, json.dumps(findings))
        findings = _parse_findings(result.stdout)
    return findings


def _stamp_language(findings: list[dict], language: str | None) -> list[dict]:
    if language is None:
        return findings
    return [{**f, "language": f.get("language", language)} for f in findings]


def _run_plugin(plugin: Plugin, project_dir: Path, scope: Scope) -> Run:
    sensed = _run_sensors(plugin.sensors, project_dir, scope)
    transformed = _apply_transformers(
        plugin.transformers, sensed.findings, project_dir, scope
    )
    return Run(_stamp_language(transformed, plugin.language), sensed.notices)


def run_sensors(
    config: Config, project_dir: Path, package_dir: Path, scope: Scope
) -> Run:
    run = Run()
    for name in config.plugins:
        plugin = _load_plugin(name, config, project_dir, package_dir)
        result = _run_plugin(plugin, project_dir, scope)
        run.findings.extend(result.findings)
        run.notices.extend(result.notices)
    transformers = [
        _resolve_part(
            config.plugins, "transformers", name, project_dir, package_dir, config
        )
        for name in config.transformers
    ]
    run.findings = _apply_transformers(transformers, run.findings, project_dir, scope)
    return run


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    project_dir = Path.cwd()
    config = load_config(project_dir, args.config)
    scope = resolve_scope(args, config, project_dir)
    run = run_sensors(config, project_dir, package_root(), scope)
    sys.stdout.write(json.dumps(run.findings) + "\n")
    for notice in run.notices:
        sys.stderr.write(notice + "\n")
    return 1 if run.failed else 0


if __name__ == "__main__":
    sys.exit(main())

"""habit-sensors: the recursive concat-then-transform ETL runner.

A node's output is ``transformers ∘ concat(child sensors)``. The root and each
plugin are the same shape: the root concatenates its plugins (each a node whose
children are its sensors), then runs the root transformers. Every plugin stamps
its declared ``language`` onto its findings.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from ..config import load_config
from ..recommend import recommendations
from ..resolve import Resolver
from ..scope import parse_args, resolve_scope
from .execution import Execution
from .loader import PluginLoader
from .model import Plugin, Run, SensorError

__all__ = ["Execution", "PluginLoader", "Plugin", "Run", "SensorError", "main"]


def _stamp_language(findings: list[dict], language: str | None) -> list[dict]:
    if language is None:
        return findings
    return [{**f, "language": f.get("language", language)} for f in findings]


def _run_plugin(plugin: Plugin, execution: Execution) -> Run:
    sensed = execution.run_sensors(plugin.sensors)
    findings, notices = execution.apply_transformers(
        plugin.transformers, sensed.findings
    )
    return Run(
        _stamp_language(findings, plugin.language), [*sensed.notices, *notices]
    )


def run_sensors(loader: PluginLoader, execution: Execution) -> Run:
    run = Run()
    for name in loader.config.plugins:
        plugin = loader.load_plugin(name)
        if plugin.language is not None:
            run.active_languages.add(plugin.language)
        result = _run_plugin(plugin, execution)
        run.findings.extend(result.findings)
        run.notices.extend(result.notices)
    transformers = [
        loader.resolve_part(loader.config.plugins, "transformers", name)
        for name in loader.config.transformers
    ]
    run.findings, notices = execution.apply_transformers(transformers, run.findings)
    run.notices.extend(notices)
    return run


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    project_dir = Path.cwd()
    config = load_config(project_dir, args.config)
    scope = resolve_scope(args, config, project_dir)
    loader = PluginLoader(Resolver.discover(project_dir), config)
    run = run_sensors(loader, Execution(project_dir, scope, args.config))
    sys.stdout.write(json.dumps(run.findings) + "\n")
    # Why the scope came out empty first: a run that measured nothing must say so
    # rather than let every sensor report clean over it.
    for notice in [*scope.notices, *run.notices]:
        sys.stderr.write(notice + "\n")
    for hint in recommendations(project_dir, scope.files, run.active_languages):
        sys.stderr.write(hint + "\n")
    return 1 if run.failed else 0


if __name__ == "__main__":
    sys.exit(main())

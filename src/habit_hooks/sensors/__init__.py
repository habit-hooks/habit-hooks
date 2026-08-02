"""habit-sensors: the recursive concat-then-transform ETL runner.

A node's output is ``transformers ∘ concat(child sensors)``. The root and each
plugin are the same shape: the root concatenates its plugins (each a node whose
children are its sensors), then runs the root transformers. Every plugin stamps
its declared ``language`` onto its findings.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..catalogue import INCOMPLETE_RUN
from ..config import Config, load_config
from ..recommend import recommendations
from ..resolve import Resolver
from ..scope import resolve_scope
from ..snooze import SNOOZE_TRANSFORMERS
from .execution import Execution
from .loader import PluginLoader
from .model import Plugin, Run, SensorError

__all__ = [
    "Execution",
    "PluginLoader",
    "Plugin",
    "Run",
    "SensorError",
    "incomplete_run_finding",
    "main",
    "parse_args",
]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="habit-sensors")
    parser.add_argument("--config", type=Path)
    # Emit findings before the snooze transformers filter them, so `--prune` sees
    # a snooze-free view of the run instead of one snooze already emptied (#94).
    parser.add_argument("--no-snooze", action="store_true")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--all", action="store_true")
    modes.add_argument("--file")
    modes.add_argument("--branch", nargs="?", const="", metavar="base")
    modes.add_argument("--last", type=int)
    modes.add_argument("--since")
    return parser.parse_args(argv)


def incomplete_run_finding(notices: list[str]) -> dict:
    """The reserved-smell finding a failed run carries on the pipe.

    A broken sensor or transformer contributes no findings of its own, so the
    mapper would see ``[]`` and render the clean guide over broken tooling (#88).
    Turning each failure notice into an ``incomplete-run`` issue makes the mapper
    coach it instead — one enforced finding that never renders as clean. It is
    appended after every transformer has run, so a snooze can never mute it.
    """
    return {
        "smell": INCOMPLETE_RUN,
        "details": {},
        "issues": [
            {"key": notice, "details": {"content": notice}} for notice in notices
        ],
    }


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


def _configure(args: argparse.Namespace, project_dir: Path) -> Config:
    """The run's config, minus the snooze transformers when ``--no-snooze`` asks.

    Stripping them here emits the run before snooze filters it, which is what
    ``habit-snooze --prune`` needs to compare its index against (#94).
    """
    config = load_config(project_dir, args.config)
    if args.no_snooze:
        config.transformers = [
            name for name in config.transformers if name not in SNOOZE_TRANSFORMERS
        ]
    return config


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    project_dir = Path.cwd()
    config = _configure(args, project_dir)
    scope = resolve_scope(args, config, project_dir)
    loader = PluginLoader(Resolver.discover(project_dir), config)
    run = run_sensors(loader, Execution(project_dir, scope, args.config))
    findings = run.findings
    if run.failed:
        findings = [*findings, incomplete_run_finding(run.notices)]
    sys.stdout.write(json.dumps(findings) + "\n")
    # Why the scope came out empty first: a run that measured nothing must say so
    # rather than let every sensor report clean over it.
    for notice in [*scope.notices, *run.notices]:
        sys.stderr.write(notice + "\n")
    for hint in recommendations(project_dir, scope.files, run.active_languages):
        sys.stderr.write(hint + "\n")
    return 1 if run.failed else 0


if __name__ == "__main__":
    sys.exit(main())

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

from ..catalogue import incomplete_run_finding
from ..cli import add_version_flag, run_console
from ..config import Config, load_config
from ..recommend import PluginStatus, recommendations
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
    "build_parser",
    "incomplete_run_finding",
    "main",
    "parse_args",
]


def _positive_int(value: str) -> int:
    """A ``--last`` count: a positive number of commits, rejected by name here so
    ``--last 0`` (an empty scope) and ``--last -1`` (``HEAD~-1``, the empty tree)
    fail loudly instead of silently scanning everything (#103)."""
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError(f"must be a positive integer, not {value!r}")
    return number


def build_parser(prog: str) -> argparse.ArgumentParser:
    """The flags a run is spelled with, under whichever binary owns them.

    ``habit-hooks`` forwards every one of these to this stage, so it builds the
    same parser under its own name to answer ``--help`` (#114) — one definition,
    so the pipeline's usage can never drift from what it actually forwards.
    """
    parser = argparse.ArgumentParser(prog=prog)
    add_version_flag(parser)
    parser.add_argument("--config", type=Path)
    # Emit findings before the snooze transformers filter them, so `--prune` sees
    # a snooze-free view of the run instead of one snooze already emptied (#94).
    parser.add_argument("--no-snooze", action="store_true")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--all", action="store_true")
    modes.add_argument("--file")
    modes.add_argument("--branch", nargs="?", const="", metavar="base")
    modes.add_argument("--last", type=_positive_int)
    modes.add_argument("--since")
    return parser


def parse_args(argv: list[str]) -> argparse.Namespace:
    return build_parser("habit-sensors").parse_args(argv)


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


def _bypasses_snooze(args: argparse.Namespace) -> bool:
    """Whether this run strips the snooze transformers before it filters findings.

    Two runs do: ``--no-snooze`` emits the run before snooze so ``--prune`` can
    compare its index against a snooze-free view (#94); and ``--file`` asks after
    one file by name, wanting its whole picture — a standing snooze is a statement
    about the backlog, not about the file you named, so it is set aside (#55).
    Only the snooze transformers are dropped, never a project's own unrelated one.
    """
    return args.no_snooze or args.file is not None


def _configure(args: argparse.Namespace, project_dir: Path) -> Config:
    """The run's config, minus the snooze transformers when the mode bypasses them."""
    config = load_config(project_dir, args.config)
    if _bypasses_snooze(args):
        config.transformers = [
            name for name in config.transformers if name not in SNOOZE_TRANSFORMERS
        ]
    return config


def main(argv: list[str] | None = None) -> int:
    return run_console("habit-sensors", _emit_findings, argv)


def _with_incomplete_run(run: Run) -> list[dict]:
    """The run's findings, plus its own ``incomplete-run`` when it failed.

    Appended after every transformer has run, so a snooze can never mute it (#88).
    """
    if run.failed:
        return [*run.findings, incomplete_run_finding(run.notices)]
    return run.findings


def _emit_findings(argv: list[str]) -> int:
    args = parse_args(argv)
    project_dir = Path.cwd()
    config = _configure(args, project_dir)
    scope = resolve_scope(args, config, project_dir)
    loader = PluginLoader(Resolver.discover(project_dir), config)
    run = run_sensors(loader, Execution(project_dir, scope, args.config))
    sys.stdout.write(json.dumps(_with_incomplete_run(run)) + "\n")
    plugins = PluginStatus(run.active_languages, loader.resolver.has_plugin)
    # Why the scope came out empty comes first: a run that measured nothing must
    # say so rather than let every sensor report clean over it. The hints follow,
    # advisory to the last — stdout and the exit code are already settled.
    for line in [
        *scope.notices,
        *run.notices,
        *recommendations(project_dir, scope.files, plugins),
    ]:
        sys.stderr.write(line + "\n")
    return 1 if run.failed else 0


if __name__ == "__main__":
    sys.exit(main())

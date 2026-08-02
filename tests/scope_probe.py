"""Ask the scope resolver what a mode decides is in scope: argv in, answer out.

The two scope test modules — ``test_scope.py`` (a mode's diagnostics) and
``test_scope_work_in_progress.py`` (which uncommitted work each mode measures) —
put the same question to ``resolve_scope``, so the phrasing lives here once.
"""

from __future__ import annotations

from pathlib import Path

from habit_hooks.config import Config
from habit_hooks.scope import Scope, resolve_scope
from habit_hooks.sensors import parse_args


def scope(argv: list[str], project_dir: Path, config: Config | None = None) -> Scope:
    return resolve_scope(parse_args(argv), config or Config(), project_dir)


def scoped_files(
    argv: list[str], project_dir: Path, config: Config | None = None
) -> list[str]:
    return scope(argv, project_dir, config).files

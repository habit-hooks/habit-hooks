"""Run a spec body through the harness and report a status per case.

Shared by the marker tests and the context tests: both drive whole spec bodies
through the real engine rather than asserting on parsed structures, because
what a marker or a nesting rule *means* is only visible once a case has run.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness import (
    POSIX_SHELL_ONLY,
    STEPS_RUN_ON_THIS_PLATFORM,
    SpecError,
    SpecFailure,
    execute,
    parse_spec,
)


def _status(test, where: Path, repo_root: Path) -> str:
    """Run one parsed test in its own dir; return "skip"/"pass"/"fail"."""
    if test.skip:
        return "skip"
    where.mkdir()
    try:
        execute(test, where, repo_root)
        return "pass"
    except (SpecFailure, SpecError):
        return "fail"


def run(text: str, tmp_path: Path, repo_root: Path | None = None) -> list[str]:
    """Parse + run a spec body, returning a status per test.

    The skip sits here rather than on either test module so the parser tests --
    which execute nothing -- still run everywhere. Only a test that reaches a
    step needs a POSIX shell.
    """
    if not STEPS_RUN_ON_THIS_PLATFORM:
        pytest.skip(POSIX_SHELL_ONLY)
    root = repo_root or tmp_path
    cases = parse_spec(text)
    return [_status(c, tmp_path / f"t{i}", root) for i, c in enumerate(cases)]

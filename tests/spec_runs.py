from __future__ import annotations

from pathlib import Path

import pytest

from harness import (
    POSIX_SHELL_ONLY,
    STEPS_RUN_ON_THIS_PLATFORM,
    Session,
    SpecError,
    SpecFailure,
    execute,
    parse_spec,
)


def _status(test, session: Session, repo_root: Path) -> str:
    if test.skip:
        return "skip"
    try:
        execute(test, session.workdir(test.continued), repo_root)
        return "pass"
    except (SpecFailure, SpecError):
        return "fail"


def run(text: str, tmp_path: Path, repo_root: Path | None = None) -> list[str]:
    if not STEPS_RUN_ON_THIS_PLATFORM:
        pytest.skip(POSIX_SHELL_ONLY)
    root = repo_root or tmp_path
    cases = parse_spec(text)
    session = Session(tmp_path)
    try:
        return [_status(case, session, root) for case in cases]
    finally:
        session.cleanup()
